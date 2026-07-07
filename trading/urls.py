from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('contact/', views.contact, name='contact'),
    path('prop-accounts/', views.prop_accounts, name='prop_accounts'),
    path('prop-orders/', views.prop_orders, name='prop_orders'),
    path('ticket-list/', views.ticket_list, name='ticket_list'),
    path('ticket/<str:ticket_number>/', views.ticket_detail, name='ticket_detail'),
    path('create-ticket/', views.create_ticket, name='create_ticket'),
    path('rules/', views.rules, name='rules'),
    path('analytics/', views.analytics, name='analytics'),
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset-verify/', views.password_reset_verify, name='password_reset_verify'),
    path('about/', views.about, name='about'),
    
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    
    path('order/<int:plan_id>/', views.order_view, name='order'),
    path('payment/<int:order_id>/', views.payment_gateway, name='payment_gateway'),
    path('get-plan-details/', views.get_plan_details, name='get_plan_details'),
    path('identity-verification/', views.identity_verification, name='identity_verification'),
    path('payment-callback/', views.payment_callback, name='payment_callback'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-error/', views.payment_error, name='payment_error'),
    path('personal-analytics/', views.personal_analytics, name='personal_analytics'),
    path('affiliate-panel/', views.affiliate_panel, name='affiliate_panel'),
    path('referral/transfer/', views.transfer_referral_to_wallet, name='transfer_referral_to_wallet'),
    path('submission/', views.user_submission_form, name='user_submission_form'),
    path('stage-upgrade-request/', views.stage_upgrade_request, name='stage_upgrade_request'),

    path('wallet/deposit/', views.wallet_deposit, name='wallet_deposit'),
    path('wallet/payment/<int:transaction_id>/', views.wallet_payment_gateway, name='wallet_payment_gateway'),
    path('wallet/success/', views.wallet_success, name='wallet_success'),
    path('wallet/error/', views.wallet_error, name='wallet_error'),
    path('generate-certificate/', views.generate_certificate, name='generate_certificate'),
    path('download-certificate/<int:certificate_id>/', views.download_certificate, name='download_certificate'),
    path('request-transfer/', views.request_transfer_to_mt4, name='request_transfer_to_mt4'),
    
]