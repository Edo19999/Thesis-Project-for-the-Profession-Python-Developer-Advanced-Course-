from django.db import models
from django.conf import settings
from django.db.models import Sum, F
import yaml


class Shop(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="shop",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255)
    external_id = models.CharField(max_length=64, blank=True, null=True)
    shops = models.ManyToManyField(Shop, related_name="categories", blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        related_name="products",
        on_delete=models.PROTECT,
    )
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(
        Product,
        related_name="offers",
        on_delete=models.CASCADE,
    )
    shop = models.ForeignKey(
        Shop,
        related_name="product_infos",
        on_delete=models.CASCADE,
    )
    external_id = models.CharField(max_length=64)
    model = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=14, decimal_places=2)
    price_rrc = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ("shop", "external_id")

    def __str__(self):
        return f"{self.shop} – {self.product} ({self.external_id})"


class Parameter(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(
        ProductInfo,
        related_name="parameters",
        on_delete=models.CASCADE,
    )
    parameter = models.ForeignKey(
        Parameter,
        related_name="product_parameters",
        on_delete=models.CASCADE,
    )
    value = models.CharField(max_length=255)

    class Meta:
        unique_together = ("product_info", "parameter")

    def __str__(self):
        return f"{self.product_info} – {self.parameter}: {self.value}"

class Contact(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="contacts",
        on_delete=models.CASCADE,
    )
    city = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.city}, {self.address}"


class Basket(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="baskets",
        on_delete=models.CASCADE,
    )
    product_info = models.ForeignKey(
        ProductInfo,
        related_name="basket_items",
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product_info")

    def __str__(self):
        return f"{self.user} – {self.product_info} x {self.quantity}"

    @property
    def amount(self):
        return self.quantity * self.product_info.price


class Order(models.Model):
    STATUS_CHOICES = (
        ("new", "Новый"),
        ("confirmed", "Подтверждён"),
        ("sent", "Отправлен"),
        ("delivered", "Доставлен"),
        ("canceled", "Отменён"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.CASCADE,
    )
    contact = models.ForeignKey(
        Contact,
        related_name="orders",
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Заказ #{self.id} ({self.user}) – {self.status}"

    @property
    def total_amount(self):
        result = self.items.aggregate(
            total=Sum(F("quantity") * F("product_info__price")),
        )["total"]
        return result or 0


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE,
    )
    product_info = models.ForeignKey(
        ProductInfo,
        related_name="order_items",
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.order} – {self.product_info} x {self.quantity}"

def import_shop_from_yaml(file_path: str):
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    shop_name = data["shop"]
    shop, _ = Shop.objects.get_or_create(name=shop_name)

    for category_data in data.get("categories", []):
        external_id = str(category_data["id"])
        name = category_data["name"]
        category, created = Category.objects.get_or_create(
            external_id=external_id,
            defaults={"name": name},
        )
        if not created and category.name != name:
            category.name = name
            category.save(update_fields=["name"])
        category.shops.add(shop)

    ProductInfo.objects.filter(shop=shop).delete()

    for item in data.get("goods", []):
        category_external_id = str(item["category"])
        category = Category.objects.get(external_id=category_external_id)

        product, _ = Product.objects.get_or_create(
            name=item["name"],
            category=category,
        )

        product_info = ProductInfo.objects.create(
            product=product,
            shop=shop,
            external_id=str(item["id"]),
            model=item.get("model", ""),
            quantity=item["quantity"],
            price=item["price"],
            price_rrc=item["price_rrc"],
        )

        for param_name, param_value in item.get("parameters", {}).items():
            parameter, _ = Parameter.objects.get_or_create(name=param_name)
            ProductParameter.objects.create(
                product_info=product_info,
                parameter=parameter,
                value=str(param_value),
            )

    return shop
