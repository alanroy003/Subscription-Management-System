from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authtoken.models import Token
from django.utils import timezone
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from core.models import Customer
from core.permissions import IsAdmin

from .apikeys import ApiKey
from .models import User
from .validators import password_problems


class AuthThrottle(AnonRateThrottle):
    rate = "20/min"

    def allow_request(self, request, view):
        return getattr(settings, "TESTING", False) or super().allow_request(request, view)


def user_payload(user: User) -> dict:
    customer = getattr(user, "customer", None)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "customer_id": customer.id if customer else None}


def _check_password(password: str) -> None:
    problems = password_problems(password or "")
    if problems:
        raise serializers.ValidationError({"password": problems})


def _check_email(email: str) -> str:
    email = (email or "").strip().lower()
    serializers.EmailField().run_validation(email)
    if User.objects.filter(email__iexact=email).exists():
        raise serializers.ValidationError({"email": ["An account with this email already exists."]})
    return email


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def signup(request):
    """Public sign-up always creates a customer; it can never create staff or admin."""
    email = _check_email(request.data.get("email"))
    password = request.data.get("password", "")
    _check_password(password)
    name = (request.data.get("name") or "").strip() or email.split("@")[0]
    with transaction.atomic():
        user = User.objects.create_user(email, password, name=name, role=User.Role.CUSTOMER)
        customer = Customer.objects.filter(email__iexact=email, user__isnull=True).first()
        if customer:
            customer.user = user
            customer.save(update_fields=["user"])
        else:
            Customer.objects.create(name=name, email=email, user=user)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": user_payload(user)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    user = authenticate(request, email=(request.data.get("email") or "").strip().lower(),
                        password=request.data.get("password", ""))
    if not user:
        return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": user_payload(user)})


@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({"detail": "Logged out."})


@api_view(["GET"])
def me(request):
    return Response(user_payload(request.user))


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def password_reset(request):
    """Always answers 200 so the endpoint cannot be used to discover accounts."""
    email = (request.data.get("email") or "").strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        send_mail("Reset your Brightloop password",
                  f"Hello {user.name or user.email},\n\nReset your password here: {link}\n\n"
                  "If you did not ask for this, ignore this email.",
                  settings.DEFAULT_FROM_EMAIL, [user.email])
    return Response({"detail": "If the email is registered, a reset link has been sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def password_reset_confirm(request):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(request.data.get("uid", ""))))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if not user or not default_token_generator.check_token(user, request.data.get("token", "")):
        return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
    password = request.data.get("password", "")
    _check_password(password)
    user.set_password(password)
    user.save()
    Token.objects.filter(user=user).delete()
    return Response({"detail": "Password updated. You can sign in now."})


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "password", "is_active", "date_joined"]
        read_only_fields = ["date_joined"]

    def validate_email(self, value):
        return _check_email(value)

    def validate_role(self, value):
        if self.instance is not None and self.instance.role == User.Role.CUSTOMER and value == User.Role.CUSTOMER:
            return value
        if value not in (User.Role.STAFF, User.Role.ADMIN):
            raise serializers.ValidationError("Only staff or admin users are created here.")
        return value

    def validate_password(self, value):
        _check_password(value)
        return value

    def create(self, data):
        return User.objects.create_user(data.pop("email"), data.pop("password"), **data)

    def update(self, user, data):
        data.pop("email", None)
        password = data.pop("password", None)
        user = super().update(user, data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["password"].required = False
            fields["email"].read_only = True
        return fields


class UserViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Only the admin can add internal staff."""

    queryset = User.objects.order_by("role", "email")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    search_fields = ["email", "name"]


class ApiKeySerializer(serializers.ModelSerializer):
    scopes = serializers.ListField(child=serializers.ChoiceField(choices=["read", "write"]), allow_empty=False)

    class Meta:
        model = ApiKey
        fields = ["id", "name", "prefix", "scopes", "created_at", "last_used_at", "revoked_at"]
        read_only_fields = ["prefix", "created_at", "last_used_at", "revoked_at"]


class ApiKeyViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Admin-only management of public API keys. The full key is returned once, on creation."""

    queryset = ApiKey.objects.select_related("created_by")
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        key, raw = ApiKey.issue(ser.validated_data["name"], sorted(set(ser.validated_data["scopes"])), request.user)
        return Response({**ApiKeySerializer(key).data, "key": raw}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        key = self.get_object()
        if not key.revoked_at:
            key.revoked_at = timezone.now()
            key.save(update_fields=["revoked_at"])
        return Response(ApiKeySerializer(key).data)
