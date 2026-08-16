from rest_framework import serializers

from .models import Course, Invoice, Student, Teacher


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Student
        exclude = ("school",)


class TeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Teacher
        exclude = ("school", "user")


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        exclude = ("school",)

    def validate_teacher(self, teacher):
        if teacher and teacher.school_id != self.context["request"].school.id:
            raise serializers.ValidationError("Teacher must belong to the active school.")
        return teacher


class InvoiceSerializer(serializers.ModelSerializer):
    paid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        exclude = ("school",)
        read_only_fields = ("status",)

    def validate_student(self, student):
        if student.school_id != self.context["request"].school.id:
            raise serializers.ValidationError("Student must belong to the active school.")
        return student
