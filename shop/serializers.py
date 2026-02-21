from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User

from .models import (
    Product,
    ProductInfo,
    Parameter,
    ProductParameter,
    Shop,
    Category,
    Contact,
    Basket,
    Order,
    OrderItem,
)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "name", "url", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "external_id"]


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.CharField(source="parameter.name")

    class Meta:
        model = ProductParameter
        fields = ["parameter", "value"]


class ProductInfoSerializer(serializers.ModelSerializer):
    shop = ShopSerializer()
    parameters = ProductParameterSerializer(many=True)

    class Meta:
        model = ProductInfo
        fields = [
            "id",
            "shop",
            "external_id",
            "model",
            "quantity",
            "price",
            "price_rrc",
            "parameters",
        ]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    offers = ProductInfoSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "offers",
        ]

class UserRegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())],
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

from .models import Contact, Basket, Order, OrderItem 

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "city", "address", "phone"]

class BasketItemSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product_info.product.name", read_only=True)
    shop = serializers.CharField(source="product_info.shop.name", read_only=True)
    price = serializers.DecimalField(
        source="product_info.price", max_digits=14, decimal_places=2, read_only=True
    )
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Basket
        fields = ["id", "product_info", "product", "shop", "quantity", "price", "amount"]
        extra_kwargs = {
            "product_info": {"write_only": True},
        }

    def get_amount(self, obj):
        return obj.amount

class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product_info.product.name", read_only=True)
    shop = serializers.CharField(source="product_info.shop.name", read_only=True)
    price = serializers.DecimalField(
        source="product_info.price", max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ["id", "product_info", "product", "shop", "quantity", "price"]
        extra_kwargs = {
            "product_info": {"write_only": True},
        }


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = Order
        fields = ["id", "status", "contact", "created_at", "updated_at", "items", "total_amount"]


class PartnerStateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


