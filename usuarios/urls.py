from django.urls import path
from . import views

urlpatterns = [
    path('get-users/', views.get_users),
    path('create-user/', views.create_user),
    path('forms-info/', views.forms_info),
    path('forms-info/<int:user_id>/', views.user_forms),
    path('get-question/<int:form_id>/', views.question),
    path('get-answer/<int:form_id>/', views.answers),
    path('get-answers/', views.get_answer),
    path('search-forms/', views.search_forms),
    path('unanswered-forms/<int:user_id>/', views.get_unanswered_forms),
    path('comments/<int:form_id>/', views.comments),
    path('comment/<int:comment_id>/', views.path_comment),
    path('likes/<int:form_id>/', views.likes)
]