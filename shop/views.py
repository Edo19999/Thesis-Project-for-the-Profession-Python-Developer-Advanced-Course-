from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from .models import (
    Product,
    Contact,
    Basket,
    Order,
    OrderItem,
    Shop,
    Category,
    ProductInfo,
    ProductParameter,
    import_shop_from_yaml,
)
from .serializers import (
    ProductSerializer,
    UserRegisterSerializer,
    UserLoginSerializer,
    ContactSerializer,
    BasketItemSerializer,
    OrderSerializer,
    PartnerStateSerializer,
)
from .tasks import send_email_task


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.all().select_related("category").prefetch_related(
            "offers__shop",
            "offers__parameters__parameter",
        )

        params = self.request.query_params

        name = params.get("name")
        if name:
            queryset = queryset.filter(name__icontains=name)

        category_id = params.get("category_id")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        category = params.get("category")
        if category:
            queryset = queryset.filter(category__name__icontains=category)

        shop_id = params.get("shop_id")
        if shop_id:
            queryset = queryset.filter(offers__shop_id=shop_id)

        price_min = params.get("price_min")
        if price_min:
            queryset = queryset.filter(offers__price__gte=price_min)

        price_max = params.get("price_max")
        if price_max:
            queryset = queryset.filter(offers__price__lte=price_max)

        queryset = queryset.distinct()

        ordering = params.get("ordering")
        if ordering == "price":
            queryset = queryset.order_by("offers__price")
        elif ordering == "-price":
            queryset = queryset.order_by("-offers__price")

        return queryset

class ProductExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        shop = Shop.objects.filter(is_active=True).first()
        if not shop:
            return Response(
                {"detail": "Нет активных магазинов"},
                status=status.HTTP_404_NOT_FOUND,
            )

        categories = Category.objects.filter(shops=shop).distinct()
        product_infos = (
            ProductInfo.objects.filter(shop=shop)
            .select_related("product", "product__category")
            .prefetch_related("parameters__parameter")
        )

        data = {
            "shop": shop.name,
            "categories": [],
            "goods": [],
        }

        for category in categories:
            category_id = category.external_id or str(category.id)
            data["categories"].append(
                {
                    "id": category_id,
                    "name": category.name,
                }
            )

        for info in product_infos:
            category = info.product.category
            category_id = category.external_id or str(category.id)
            item_id = info.external_id or str(info.id)

            parameters = {}
            for param in info.parameters.all():
                parameters[param.parameter.name] = param.value

            data["goods"].append(
                {
                    "id": item_id,
                    "name": info.product.name,
                    "category": category_id,
                    "model": info.model,
                    "quantity": info.quantity,
                    "price": float(info.price),
                    "price_rrc": float(info.price_rrc),
                    "parameters": parameters,
                }
            )

        return Response(data)

class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.all().select_related("category").prefetch_related(
        "offers__shop",
        "offers__parameters__parameter",
    )
    serializer_class = ProductSerializer

class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        send_email_task.delay(
            "Регистрация в сервисе заказов",
            "Вы успешно зарегистрировались в сервисе заказов.",
            [user.email],
        )


class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {"detail": "Неверные учетные данные"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})
        

class ContactListCreateView(generics.ListCreateAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ContactDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)


class BasketView(generics.GenericAPIView):
    serializer_class = BasketItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user).select_related(
            "product_info__product",
            "product_info__shop",
        )

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        total = sum(item.amount for item in self.get_queryset())
        return Response({"items": serializer.data, "total_amount": total})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_info = serializer.validated_data["product_info"]
        quantity = serializer.validated_data["quantity"]

        basket_item, created = Basket.objects.get_or_create(
            user=request.user,
            product_info=product_info,
            defaults={"quantity": quantity},
        )
        if not created:
            basket_item.quantity = quantity
            basket_item.save(update_fields=["quantity"])

        return Response(self.get_serializer(basket_item).data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        item_id = request.data.get("id")
        if not item_id:
            return Response(
                {"detail": "Нужно передать id позиции корзины"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = self.get_queryset().get(id=item_id)
        except Basket.DoesNotExist:
            return Response(
                {"detail": "Позиция не найдена"},
                status=status.HTTP_404_NOT_FOUND,
            )

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related(
            "items__product_info__product",
            "items__product_info__shop",
        )

    def perform_create(self, serializer):
        contact_id = self.request.data.get("contact")
        if not contact_id:
            raise serializers.ValidationError({"contact": "Обязательное поле"})

        try:
            contact = Contact.objects.get(id=contact_id, user=self.request.user)
        except Contact.DoesNotExist:
            raise serializers.ValidationError({"contact": "Контакт не найден"})

        basket_items = Basket.objects.filter(user=self.request.user)
        if not basket_items.exists():
            raise serializers.ValidationError({"basket": "Корзина пуста"})

        order = serializer.save(user=self.request.user, contact=contact)

        order_items = [
            OrderItem(
                order=order,
                product_info=item.product_info,
                quantity=item.quantity,
            )
            for item in basket_items
        ]
        OrderItem.objects.bulk_create(order_items)
        basket_items.delete()

        total = order.total_amount

        send_email_task.delay(
            f"Заказ #{order.id} принят",
            f"Ваш заказ #{order.id} успешно оформлен. Сумма: {total}.",
            [order.user.email],
        )

        send_email_task.delay(
            f"Новый заказ #{order.id}",
            f"Поступил новый заказ #{order.id} от пользователя {order.user.username}. Сумма: {total}.",
            [settings.ADMIN_EMAIL],
        )


class OrderDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related(
            "items__product_info__product",
            "items__product_info__shop",
        )

    def perform_update(self, serializer):
        order = self.get_object()
        old_status = order.status
        order = serializer.save()

        if order.status != old_status:
            total = order.total_amount
            send_email_task.delay(
                f"Статус заказа #{order.id} изменён",
                f"Статус вашего заказа #{order.id} изменён на '{order.get_status_display()}'. Сумма: {total}.",
                [order.user.email],
            )


class PartnerStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            shop = Shop.objects.get(user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Для пользователя не привязан магазин"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "id": shop.id,
                "name": shop.name,
                "is_active": shop.is_active,
            }
        )

    def post(self, request, *args, **kwargs):
        try:
            shop = Shop.objects.get(user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Для пользователя не привязан магазин"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PartnerStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop.is_active = serializer.validated_data["is_active"]
        shop.save(update_fields=["is_active"])

        return Response(
            {
                "id": shop.id,
                "name": shop.name,
                "is_active": shop.is_active,
            }
        )


class PartnerOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            shop = Shop.objects.get(user=self.request.user)
        except Shop.DoesNotExist:
            return Order.objects.none()

        return (
            Order.objects.filter(items__product_info__shop=shop)
            .distinct()
            .prefetch_related(
                "items__product_info__product",
                "items__product_info__shop",
            )
        )


class PartnerImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        file_path = request.data.get("file_path")
        if not file_path:
            return Response(
                {"detail": "Нужно передать file_path с путём до YAML-файла"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        full_path = settings.BASE_DIR / file_path

        try:
            shop = import_shop_from_yaml(str(full_path))
        except FileNotFoundError:
            return Response(
                {"detail": f"Файл не найден: {full_path}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": f"Ошибка импорта: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shop.user is None:
            shop.user = request.user
            shop.save(update_fields=["user"])

        return Response(
            {
                "id": shop.id,
                "name": shop.name,
                "url": shop.url,
                "is_active": shop.is_active,
            }
        )


class AdminImportTaskView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        file_path = request.data.get("file_path")
        if not file_path:
            return Response(
                {"detail": "Нужно передать file_path с путём до YAML-файла"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import do_import

        async_result = do_import.delay(str(settings.BASE_DIR / file_path))

        return Response(
            {
                "task_id": async_result.id,
                "status": async_result.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )
