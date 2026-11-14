from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import reports, views

router = DefaultRouter()
router.register("teachers", views.TeacherViewSet, basename="teacher")
router.register("rooms", views.RoomViewSet, basename="room")
router.register("students", views.StudentViewSet, basename="student")
router.register("groups", views.GroupViewSet, basename="group")
router.register("enrollments", views.EnrollmentViewSet, basename="enrollment")
router.register("lessons", views.LessonViewSet, basename="lesson")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("refunds", views.RefundViewSet, basename="refund")
router.register("salaries", views.SalaryViewSet, basename="salary")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("settings", views.SettingsView, basename="settings")

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/me/", views.me),
    path("reports/dashboard/", reports.dashboard),
    path("reports/debtors/", reports.debtors),
    path("reports/attendance/", reports.attendance_report),
    path("reports/export/<str:kind>/", reports.export),
    path("public/receipt/<uuid:token>/", views.public_receipt),
    path("", include(router.urls)),
]
