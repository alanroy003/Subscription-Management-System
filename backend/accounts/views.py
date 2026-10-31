from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from core import audit
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


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=User.Role.choices)
    customer_id = serializers.IntegerField(allow_null=True)


class AuthResponseSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Send as `Authorization: Token <token>`")
    user = MeSerializer()


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(help_text="More than 8 characters with upper, lower and a special character")
    name = serializers.CharField(required=False, help_text="Company or person name; defaults to the email name")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField()


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


AUTH = ["auth"]


@extend_schema(
    tags=AUTH, summary="Sign up as a customer", request=SignupSerializer,
    responses={201: AuthResponseSerializer, 400: OpenApiResponse(description="Invalid email or weak password")},
)
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
        audit.record("auth.signup", user, actor=user)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": user_payload(user)}, status=status.HTTP_201_CREATED)


@extend_schema(tags=AUTH, summary="Sign in and get a token", request=LoginSerializer,
               responses={200: AuthResponseSerializer, 400: DetailSerializer})
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    email = (request.data.get("email") or "").strip().lower()
    user = authenticate(request, email=email, password=request.data.get("password", ""))
    if not user:
        audit.record("auth.login_failed", object_type="user", ref=email[:100])
        return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
    token, _ = Token.objects.get_or_create(user=user)
    audit.record("auth.login", user, actor=user)
    return Response({"token": token.key, "user": user_payload(user)})


@extend_schema(tags=AUTH, summary="Sign out (invalidates the token)", request=None, responses={200: DetailSerializer})
@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    audit.record("auth.logout", request.user)
    return Response({"detail": "Logged out."})


@extend_schema(tags=AUTH, summary="Who am I", responses={200: MeSerializer})
@api_view(["GET"])
def me(request):
    return Response(user_payload(request.user))


@extend_schema(tags=AUTH, summary="Email a password reset link", request=EmailSerializer,
               responses={200: DetailSerializer})
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
        audit.record("auth.password_reset_requested", user, actor=user)
    return Response({"detail": "If the email is registered, a reset link has been sent."})


@extend_schema(tags=AUTH, summary="Set a new password from a reset link", request=ResetConfirmSerializer,
               responses={200: DetailSerializer, 400: DetailSerializer})
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
    with transaction.atomic():
        user.set_password(password)
        user.save()
        Token.objects.filter(user=user).delete()
        audit.record("auth.password_reset", user, actor=user)
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


class UserViewSet(audit.AuditedModelViewSetMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Only the admin can add internal staff."""

    queryset = User.objects.order_by("role", "email")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    search_fields = ["email", "name"]
    audit_name = "user"


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
        with transaction.atomic():
            key, raw = ApiKey.issue(ser.validated_data["name"], sorted(set(ser.validated_data["scopes"])), request.user)
            audit.record("api_key.created", key, ref=f"{key.name} (bl_{key.prefix})", changes={"scopes": key.scopes})
        return Response({**ApiKeySerializer(key).data, "key": raw}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        key = self.get_object()
        if not key.revoked_at:
            with transaction.atomic():
                key.revoked_at = timezone.now()
                key.save(update_fields=["revoked_at"])
                audit.record("api_key.revoked", key, ref=f"{key.name} (bl_{key.prefix})")
        return Response(ApiKeySerializer(key).data)
