from rest_framework import serializers
from core.models import Book, BookIssuance, BookRequest, BookReservation, Category, Department, Fine, Language, MemberProfile, User
from core.serializers import DepartmentSerializer, LanguageSerializer, SessionSettingsSerializer


class BookReservationSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = BookReservation
        fields = [
            'id', 'user', 'book', 'book_title', 'user_name',
            'reserved_at', 'reserved_from', 'reserved_to',
            'notes', 'agreed', 'status',
        ]
        read_only_fields = ['id', 'user', 'reserved_at', 'status']
    
    def validate(self, attrs):
        user = self.context['request'].user
        book = attrs['book']
        r_from = attrs['reserved_from']
        r_to = attrs['reserved_to']
        if not r_to or not r_from:
            raise serializers.ValidationError({"detail": "reserved_to Or reserved_from fields are missing" 
            })
        if BookReservation.objects.filter(
              user=user, book=book, status='PENDING'
           ).exists():
            raise serializers.ValidationError({
              "book": "You already have an active reservation for this book."
            })
        return attrs


class BulkBookUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    author = serializers.CharField(max_length=255)
    isbn = serializers.CharField(max_length=13)
    category = serializers.CharField(required=False)
    total_copies = serializers.IntegerField(min_value=1)

    def validate_isbn(self, value):
        if Book.objects.filter(isbn=value).exists():
            raise serializers.ValidationError(
                "Book with this ISBN already exists.")
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class FineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fine
        fields = '__all__'


class BookRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookRequest
        fields = '__all__'
        read_only_fields = ['user', 'status', 'requested_at', 'responded_at']


class BookIssuanceDetailSerializer(serializers.ModelSerializer):
    book = serializers.SerializerMethodField()
    member = serializers.SerializerMethodField()

    class Meta:
        model = BookIssuance
        fields = '__all__'

    def get_book(self, obj):
        return {
            "id": obj.book.id,
            "title": obj.book.title,
            "price": obj.book.price
        }

    def get_member(self, obj):
        return {
            "id": obj.member.id,
            "name":  obj.member.username or obj.member.get_full_name()
        }

    def validate(self, data):
        book = data['book']
        member = data['member']

        if book.available_copies < 1:
            raise serializers.ValidationError(
                "No available copies for this book.")

        if BookIssuance.objects.filter(book=book, member=member, returned_at__isnull=True).exists():
            raise serializers.ValidationError(
                "This member already has this book issued and not returned.")

        return data


class BookIssuanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookIssuance
        fields = '__all__'


class BookSerializer(serializers.ModelSerializer):
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all())
    language = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all())
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all())

    class Meta:
        model = Book
        fields = [
            'title', 'author', 'isbn', 'department', 'category',
            'language', 'publisher', 'edition', 'total_copies',
            'rack_no', 'shelf_location', 'date_of_entry',
            'brief_description', 'detailed_description',
            'cover_photo', 'ebook_file', 'status', 'price'
        ]


class BookDetailSerializer(serializers.ModelSerializer):
    language = LanguageSerializer()
    category = CategorySerializer()
    department = DepartmentSerializer()

    class Meta:
        model = Book
        fields = '__all__'
