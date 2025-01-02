import json
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import User, Form, Question, Answer, Comment, Like
from django.contrib.auth.hashers import make_password, check_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.contrib.postgres.search import SearchVector, TrigramSimilarity
from django.db.models import Q
from django.db import connection

# Create your views here.
@csrf_exempt
def get_users(request):
    if request.method == "GET":
        users = list(User.objects.all().values())

        response = []
        for user in users:
            response.append({
                'id': user['id'],
                'name': user['name'],
                'role': user['role'],
                'email': user['email'],
                'last_login': user['last_login']
            })

        return JsonResponse(response, safe=False, status=200)
    if request.method == "POST":
        return log_in(request)
    if request.method == 'PUT':
        return update_user(request)

@csrf_exempt
def create_user(request):
    if request.method == "POST":
        return new_user(request)


def search_forms(request):
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    query = request.GET.get('query', '').strip()
    if not query:
        return JsonResponse({'error': 'Query parameter is required'}, status=400)
    
    results = Form.objects.annotate(
        search=SearchVector('title', 'description'),
        similarity=TrigramSimilarity('title', query) 
    ).filter(
        Q(search__icontains=query) |  
        Q(similarity__gt=0.3)  
    ).distinct().order_by('-similarity')  

    response = [{
        'id': form.id, 
        'title': form.title,
        'description': form.description,
        'status': form.status,
        'created_at': form.created_at,
        'updated_at': form.updated_at,
        'user_id': form.user_id,
        'name': User.objects.get(id=form.user_id).name} 
        for form in results
    ]
    return JsonResponse(response, safe=False)

@csrf_exempt
@api_view(['GET', 'POST', 'DELETE', 'PUT'])
@permission_classes([IsAuthenticated])
def forms_info(request):
    if request.method == 'GET':
        return get_forms(request)
    elif request.method == 'POST':
        return create_form(request)
    elif request.method == "DELETE":
        return delete_form(request)
    elif request.method == 'PUT':
        return update_form(request)

@api_view(['GET', 'POST', 'DELETE', 'PUT'])
@permission_classes([IsAuthenticated])
def user_forms(request, user_id):
    if request.method == 'GET':
        forms = list(Form.objects.filter(user_id=user_id).values())
        user_name = User.objects.get(id=user_id).name
        response = []
        for form in forms:
            response.append({
                'id': form['id'],
                'name': user_name,
                'title': form['title'],
                'description': form['description'],
                'status': form['status'],
                'created_at': form['created_at'],
                'updated_at': form['updated_at'],
            })

        return JsonResponse(response, safe=False, status=200)

@csrf_exempt
@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def question(request, form_id):
    if request.method == "GET":
        return get_question(request, form_id)
    elif request.method == "POST":
        return create_questions(request, form_id)
    elif request.method == "PUT":
        return update_question(request, form_id)

@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def answers(request, form_id):
    if request.method == "GET":
        return get_answers(request, form_id)
    elif request.method == "POST":
        return create_answers(request, form_id)
    
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])   
def comments(request, form_id):
    if request.method == 'POST':
        return new_comment(request, form_id)
    elif request.method == 'GET':
        return get_comments(request, form_id)

@api_view(['DELETE', 'PUT'])
@permission_classes([IsAuthenticated]) 
def path_comment(request, comment_id):
    if request.method == 'DELETE':
        return delete_comment(request, comment_id)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated]) 
def likes(request, form_id):
    if request.method == 'POST':
        return give_like(request, form_id)
    elif request.method == 'GET':
        return get_likes(request, form_id)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_answer(request):
    if request.method == "GET":
        data = Answer.objects.all().values('form_id', 'user_id', 'created_at')

        response_data = []
        seen = set()

        for item in data:
            unique_key = (item['form_id'], item['user_id'])
            
            if unique_key in seen:
                continue  

            form_title = Form.objects.get(id=item["form_id"]).title
            user_name = User.objects.get(id=item["user_id"]).name

            response_data.append({
                'id': item['form_id'],
                'title': form_title, 
                'created_at': item['created_at'],
                'name': user_name 
            })

            seen.add(unique_key)

        return JsonResponse(response_data, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unanswered_forms(request, user_id):
    if request.method == "GET":
        data = Form.objects.filter(~Q(id__in=Answer.objects.filter(user_id=user_id).values('form_id'))).values()

        response = []
        for form in data:
            response.append({
                'id': form['id'],
                'name': User.objects.get(id=form['user_id']).name,
                'title': form['title'],
                'description': form['description'],
                'status': form['status'],
                'created_at': form['created_at'],
                'updated_at': form['updated_at'],
            })

        return JsonResponse(response, safe=False)
    
# Factions Views
# forms functions
def get_forms(request):
    forms = list(Form.objects.all().values())

    response = []
    for form in forms:
        try:
            user = User.objects.get(id=form['user_id'])
            response.append({
                'id': form['id'],
                'name': user.name,
                'title': form['title'],
                'description': form['description'],
                'status': form['status'],
                'created_at': form['created_at'],
                'updated_at': form['updated_at'],
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    return JsonResponse(response, safe=False, status=200)

def create_form(request):
    data = json.loads(request.body)
    form = Form.objects.create(
        user_id=data['user_id'],
        title=data['title'],
        description=data['description'],
    )
    response = {
        'id': form.id,
        'name': User.objects.get(id=data['user_id']).name,
        'title': form.title,
        'description': form.description,
        'status': form.status,
        'created_at': form.created_at,
        'updated_at': form.updated_at,
    }

    return JsonResponse(response, safe=False, status=201)

def delete_form(request):
    data = json.loads(request.body)
    form = Form.objects.get(id=data['id'])
    form.delete()

    return JsonResponse('Delete Successfully', safe=False)

def update_form(request):
    data = json.loads(request.body)
    form = Form.objects.get(id=data['id'])
    form.title = data['title']
    form.description = data['description']
    form.updated_at = timezone.now()
    form.status = data['status']
    form.save()

    response = {
        'message': "Updated successfully",
        'data': {
            'id': data['id'],
            'name': form.user.name,
            'title': form.title,
            'description': form.description,
            'status': form.status,
            'created_at': form.created_at,
            'updated_at': form.updated_at,
        }
    }

    return JsonResponse( response, safe=False)

# Questions functions
def get_question(request, form_id):
    try:
        form_name = Form.objects.get(id=form_id)
    except Form.DoesNotExist:
        return JsonResponse({'error': 'Form not found'}, status=404)

    data = Question.objects.filter(form_id=form_id)

    if not data.exists():
        return JsonResponse({'message': 'No questions found for this form'}, status=404)

    response = []
    for question in data:
        response.append({
            'form_title': form_name.title,
            'question_id': question.id,
            'form_id': question.form_id,
            'question': question.question,
            'type': question.type,
            'options': question.options or [],
            'created_at': question.created_at,
            'updated_at': question.updated_at,
            'description': Form.objects.get(id=form_id).description
        })

    return JsonResponse(response, safe=False)

def create_questions(request, form_id):
    data = json.loads(request.body)
    get_object_or_404(Form, id=form_id)

    response = []
    for question in data:
        new_question = Question.objects.create(
            form_id=form_id,
            type=question['type'],
            question=question['question'],
            options=question.get('options', None),
            required=question['required'],
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        response.append({
            'id': new_question.id,
            'type': new_question.type,
            'form_id': new_question.form_id,
            'question': new_question.question,
            'options': new_question.options,
            'created_at': new_question.created_at,
            'updated_at': new_question.updated_at,
        })

    return JsonResponse(response, safe=False, status=201)

def update_question(request, form_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    response = []
    for question in data:
        required_fields = ['question', 'type']
        missing_fields = [field for field in required_fields if field not in question]
        if missing_fields:
            response.append({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}",
                "question_id": question.get('question_id')
            })
            continue

        if 'question_id' in question and question['question_id']:
            try:
                question_instance = Question.objects.get(id=question['question_id'], form_id=form_id)
                question_instance.question = question['question']
                question_instance.type = question['type']
                question_instance.options = question['options']
                question_instance.required = question.get('required', question_instance.required)
                question_instance.updated_at = timezone.now()
                question_instance.save()

                response.append({"status": "updated", "question_id": question_instance.id})
            except Question.DoesNotExist:
                new_question = Question.objects.create(
                    form_id=form_id,
                    question=question['question'],
                    type=question['type'],
                    options=question.get('options', None),
                    required=question.get('required', True),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                response.append({"status": "created", "question_id": new_question.id})
        else:
            new_question = Question.objects.create(
                form_id=form_id,
                question=question['question'],
                type=question['type'],
                options=question.get('options', None),
                required=question.get('required', True),
                created_at=timezone.now(),
                updated_at=timezone.now(),
            )
            response.append({"status": "created", "question_id": new_question.id})

    return JsonResponse(response, safe=False)

# ANSWER FUNCTION
def get_answers(request, form_id):
    data = Answer.objects.filter(form_id=form_id)
    user_name = data[0].user.name
    response = []
    for answer in data:
        question = Question.objects.get(id=answer.question_id).question
        form_title = Form.objects.get(id=answer.form_id).title
        response.append({
            'id': answer.id,
            'question_id': question,
            'form_id': form_title,
            'user_name': user_name,
            'answer': answer.answer,
            'created_at': answer.created_at,
            })
        
    return JsonResponse(response, safe=False)

def create_answers(request, form_id):
    data = json.loads(request.body)

    response = []
    for answer in data:
        new_answer = Answer.objects.create(
            form_id=form_id,
            question_id=answer['question_id'],
            user_id=answer['user_id'],
            answer=answer['answer'],
            created_at=timezone.now(),
        )
        response.append({
            'id': new_answer.id,
            'form_id': new_answer.form_id,
            'question_id': new_answer.question_id,
            'user_id': new_answer.user_id,
            'answer': new_answer.answer,
            'created_at': new_answer.created_at,
        })

    return JsonResponse(response, safe=False)

# User functions
def new_user(request):
    data = json.loads(request.body)

    if User.objects.filter(email=data['email']).exists():
        return JsonResponse({"error": "El email ya existe"}, status=400)
    
    user = User.objects.create(
        name=data['name'],
        email=data['email'],
        password=make_password(data['password']),
        created_at=timezone.now(),
    )

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response = {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'password': user.password,
        'created_at': user.created_at,
        'access_token': access_token,
        'refresh_token': refresh_token
    }

    return JsonResponse(response, safe=False, status=201)

def log_in(request):
    try:
        item = json.loads(request.body)
        if 'email' not in item or 'password' not in item:
            return JsonResponse({'error': 'Faltan datos'}, status=400)

        email = item.get('email')
        password = item.get('password')

        try:
            user = User.objects.get(email=email)
            user.last_login = timezone.now()
            user.save()
        except User.DoesNotExist:
            return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
        
        if check_password(password, user.password):
            # Generar los tokens JWT
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            response_data = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'access': access_token,
                'refresh': refresh_token,
            }
            
            return JsonResponse(response_data, status=200, safe=False)
        else:
            return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
def update_user(request):
    data = json.loads(request.body)
    user = get_object_or_404(User, id=data['id'])

    user.role = data['role']
    user.save()

    return JsonResponse('Update Success', safe=False)

# Comments functions
def new_comment(request, form_id):
    data = json.loads(request.body)
    form = get_object_or_404(Form, id=form_id)

    comment = Comment.objects.create(
        form_id=form_id,
        user_id=data['user_id'],
        comment=data['comment'],
        created_at=timezone.now(),
        updated_at=timezone.now(),
    )

    response = {
        'id': comment.id,
        'form_id': comment.form_id,
        'name': User.objects.get(id=comment.user_id).name,
        'comment': comment.comment,
        'created_at': comment.created_at,
        'updated_at': comment.updated_at,
        'comment': comment.comment
    }

    return JsonResponse(response, safe=False, status=201)

def get_comments(request, form_id):
    comments = Comment.objects.filter(form_id=form_id).values()

    response = []
    for item in comments:
        response.append({
            'id': item['id'],
            'form_id': item['form_id'],
            'name': User.objects.get(id=item['user_id']).name,
            'created_at': item['created_at'],
            'updated_at': item['updated_at'],
            'comment': item['comment']
        })

    return JsonResponse(response, safe=False)

def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    comment.delete()

    return JsonResponse("Deleted successfully", safe=False)

# Likes functions
def give_like(request, form_id):
    user = request.user
    form = Form.objects.get(id=form_id)

    if Like.objects.filter(user=user, form=form).exists():
        return JsonResponse({"message": "You already liked this form."}, status=400)
    
    Like.objects.create(user=user, form=form)
    new_count = Like.objects.filter(form_id=form_id).count()
    return JsonResponse({"message": "Like added successfully", "likes_count": new_count}, status=201)

def get_likes(request, form_id):
    likes_count = Like.objects.filter(form_id=form_id).count()
    return JsonResponse({"likes_count": likes_count})