from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import jwt
import secrets
from io import BytesIO
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from database import supabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
SECRET_KEY = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

app = FastAPI()
api_router = APIRouter(prefix="/api")

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    email: str
    role: str
    created_at: str

class CourseCreate(BaseModel):
    name: str
    code: str
    description: str
    academic_period: str

class Course(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    code: str
    description: str
    teacher_id: str
    academic_period: str
    access_code: str
    created_at: str

class EnrollmentCreate(BaseModel):
    access_code: str

class GradeInput(BaseModel):
    enrollment_id: str
    corte1: Optional[float] = None
    corte2: Optional[float] = None
    corte3: Optional[float] = None

class Grade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    enrollment_id: str
    course_id: str
    student_id: str
    student_name: str
    corte1: Optional[float] = None
    corte2: Optional[float] = None
    corte3: Optional[float] = None
    final_grade: Optional[float] = None
    last_updated: str

class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    message: str
    type: str
    read: bool
    created_at: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        response = supabase.table("users").select("id, full_name, email, role, created_at").eq("id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=401, detail="User not found")
        return response.data[0]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def calculate_final_grade(corte1: Optional[float], corte2: Optional[float], corte3: Optional[float]) -> Optional[float]:
    if corte1 is not None and corte2 is not None and corte3 is not None:
        final = (corte1 * 0.3) + (corte2 * 0.35) + (corte3 * 0.35)
        return round(final, 2)
    return None

async def create_notification(user_id: str, message: str, notification_type: str):
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "message": message,
        "type": notification_type,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("notifications").insert(notification).execute()

@api_router.get("/")
async def root():
    return {"message": "Sistema de Gestión Académica API"}

@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    response = supabase.table("users").select("id").eq("email", user_data.email).execute()
    if response.data:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    if user_data.role not in ["teacher", "student"]:
        raise HTTPException(status_code=400, detail="Rol inválido")

    user = {
        "id": str(uuid.uuid4()),
        "full_name": user_data.full_name,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "role": user_data.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reset_token": None,
        "reset_token_expiry": None
    }

    supabase.table("users").insert(user).execute()

    access_token = create_access_token(data={"sub": user["id"]})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    response = supabase.table("users").select("*").eq("email", credentials.email).execute()
    if not response.data or not verify_password(credentials.password, response.data[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    user = response.data[0]
    access_token = create_access_token(data={"sub": user["id"]})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    response = supabase.table("users").select("id").eq("email", request.email).execute()
    if not response.data:
        return {"message": "Si el correo existe, recibirás un enlace de recuperación"}

    user = response.data[0]
    reset_token = secrets.token_urlsafe(32)
    reset_token_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    supabase.table("users").update({
        "reset_token": reset_token,
        "reset_token_expiry": reset_token_expiry
    }).eq("id", user["id"]).execute()

    return {
        "message": "Si el correo existe, recibirás un enlace de recuperación",
        "reset_token": reset_token
    }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    response = supabase.table("users").select("*").eq("reset_token", request.token).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Token inválido")

    user = response.data[0]
    if user["reset_token_expiry"]:
        expiry = datetime.fromisoformat(user["reset_token_expiry"])
        if expiry < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Token expirado")

    new_password_hash = hash_password(request.new_password)
    supabase.table("users").update({
        "password_hash": new_password_hash,
        "reset_token": None,
        "reset_token_expiry": None
    }).eq("id", user["id"]).execute()

    return {"message": "Contraseña actualizada exitosamente"}

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    return User(**current_user)

@api_router.post("/courses", response_model=Course)
async def create_course(course_data: CourseCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes pueden crear cursos")

    response = supabase.table("courses").select("id").eq("code", course_data.code).execute()
    if response.data:
        raise HTTPException(status_code=400, detail="El código del curso ya existe")

    course = {
        "id": str(uuid.uuid4()),
        "name": course_data.name,
        "code": course_data.code,
        "description": course_data.description,
        "teacher_id": current_user["id"],
        "academic_period": course_data.academic_period,
        "access_code": secrets.token_urlsafe(8),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    supabase.table("courses").insert(course).execute()
    return Course(**course)

@api_router.get("/courses/teacher", response_model=List[Course])
async def get_teacher_courses(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    response = supabase.table("courses").select("*").eq("teacher_id", current_user["id"]).execute()
    return [Course(**course) for course in response.data]

@api_router.get("/courses/student", response_model=List[Course])
async def get_student_courses(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(status_code=403, detail="Solo estudiantes")

    enrollments = supabase.table("enrollments").select("course_id").eq("student_id", current_user["id"]).execute()
    if not enrollments.data:
        return []

    course_ids = [e["course_id"] for e in enrollments.data]
    response = supabase.table("courses").select("*").in_("id", course_ids).execute()
    return [Course(**course) for course in response.data]

@api_router.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    course = response.data[0]

    if current_user["role"] == "teacher":
        if course["teacher_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="No autorizado")
    else:
        enrollment = supabase.table("enrollments").select("id").eq("student_id", current_user["id"]).eq("course_id", course_id).execute()
        if not enrollment.data:
            raise HTTPException(status_code=403, detail="No inscrito en este curso")

    return Course(**course)

@api_router.put("/courses/{course_id}", response_model=Course)
async def update_course(course_id: str, course_data: CourseCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    response = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not response.data or response.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    supabase.table("courses").update({
        "name": course_data.name,
        "code": course_data.code,
        "description": course_data.description,
        "academic_period": course_data.academic_period
    }).eq("id", course_id).execute()

    updated = supabase.table("courses").select("*").eq("id", course_id).execute()
    return Course(**updated.data[0])

@api_router.delete("/courses/{course_id}")
async def delete_course(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    response = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not response.data or response.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    supabase.table("grades").delete().eq("course_id", course_id).execute()
    supabase.table("enrollments").delete().eq("course_id", course_id).execute()
    supabase.table("courses").delete().eq("id", course_id).execute()

    return {"message": "Curso eliminado"}

@api_router.post("/courses/enroll")
async def enroll_in_course(enrollment_data: EnrollmentCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(status_code=403, detail="Solo estudiantes")

    response = supabase.table("courses").select("*").eq("access_code", enrollment_data.access_code).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Código de acceso inválido")

    course = response.data[0]

    existing = supabase.table("enrollments").select("id").eq("student_id", current_user["id"]).eq("course_id", course["id"]).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Ya estás inscrito en este curso")

    enrollment = {
        "id": str(uuid.uuid4()),
        "student_id": current_user["id"],
        "course_id": course["id"],
        "enrolled_at": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("enrollments").insert(enrollment).execute()

    grade = {
        "id": str(uuid.uuid4()),
        "enrollment_id": enrollment["id"],
        "course_id": course["id"],
        "student_id": current_user["id"],
        "student_name": current_user["full_name"],
        "corte1": None,
        "corte2": None,
        "corte3": None,
        "final_grade": None,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("grades").insert(grade).execute()

    return {"message": "Inscripción exitosa", "course": Course(**course)}

@api_router.get("/courses/{course_id}/students")
async def get_course_students(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    response = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not response.data or response.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    enrollments = supabase.table("enrollments").select("student_id").eq("course_id", course_id).execute()
    if not enrollments.data:
        return []

    student_ids = [e["student_id"] for e in enrollments.data]
    students = supabase.table("users").select("id, full_name, email, role, created_at").in_("id", student_ids).execute()

    return students.data

@api_router.post("/grades")
async def create_or_update_grade(grade_data: GradeInput, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    for grade_value in [grade_data.corte1, grade_data.corte2, grade_data.corte3]:
        if grade_value is not None and (grade_value < 0 or grade_value > 5):
            raise HTTPException(status_code=400, detail="Las notas deben estar entre 0.0 y 5.0")

    enrollment = supabase.table("enrollments").select("*").eq("id", grade_data.enrollment_id).execute()
    if not enrollment.data:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    course = supabase.table("courses").select("*").eq("id", enrollment.data[0]["course_id"]).execute()
    if not course.data or course.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    existing_grade = supabase.table("grades").select("*").eq("enrollment_id", grade_data.enrollment_id).execute()

    update_data = {"last_updated": datetime.now(timezone.utc).isoformat()}
    if grade_data.corte1 is not None:
        update_data["corte1"] = grade_data.corte1
    if grade_data.corte2 is not None:
        update_data["corte2"] = grade_data.corte2
    if grade_data.corte3 is not None:
        update_data["corte3"] = grade_data.corte3

    corte1 = grade_data.corte1 if grade_data.corte1 is not None else existing_grade.data[0].get("corte1")
    corte2 = grade_data.corte2 if grade_data.corte2 is not None else existing_grade.data[0].get("corte2")
    corte3 = grade_data.corte3 if grade_data.corte3 is not None else existing_grade.data[0].get("corte3")

    final_grade = calculate_final_grade(corte1, corte2, corte3)
    if final_grade is not None:
        update_data["final_grade"] = final_grade

    supabase.table("grades").update(update_data).eq("enrollment_id", grade_data.enrollment_id).execute()

    background_tasks.add_task(
        create_notification,
        enrollment.data[0]["student_id"],
        f"Nueva calificación registrada en {course.data[0]['name']}",
        "grade_update"
    )

    updated_grade = supabase.table("grades").select("*").eq("enrollment_id", grade_data.enrollment_id).execute()
    return Grade(**updated_grade.data[0])

@api_router.get("/grades/course/{course_id}", response_model=List[Grade])
async def get_course_grades(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    course = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not course.data or course.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    grades = supabase.table("grades").select("*").eq("course_id", course_id).execute()
    return [Grade(**grade) for grade in grades.data]

@api_router.get("/grades/student/course/{course_id}", response_model=Grade)
async def get_student_grade(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(status_code=403, detail="Solo estudiantes")

    grade = supabase.table("grades").select("*").eq("course_id", course_id).eq("student_id", current_user["id"]).execute()

    if not grade.data:
        raise HTTPException(status_code=404, detail="Calificación no encontrada")

    return Grade(**grade.data[0])

@api_router.get("/grades/export/{course_id}")
async def export_grades_pdf(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Solo docentes")

    course = supabase.table("courses").select("*").eq("id", course_id).execute()
    if not course.data or course.data[0]["teacher_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    grades = supabase.table("grades").select("*").eq("course_id", course_id).execute()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title = Paragraph(f"<b>Reporte de Calificaciones</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    course_info = Paragraph(f"<b>Curso:</b> {course.data[0]['name']} ({course.data[0]['code']})<br/><b>Período:</b> {course.data[0]['academic_period']}", styles['Normal'])
    elements.append(course_info)
    elements.append(Spacer(1, 12))

    data = [['Estudiante', 'Corte 1 (30%)', 'Corte 2 (35%)', 'Corte 3 (35%)', 'Nota Final']]

    for grade in grades.data:
        row = [
            grade['student_name'],
            str(grade['corte1']) if grade['corte1'] is not None else '-',
            str(grade['corte2']) if grade['corte2'] is not None else '-',
            str(grade['corte3']) if grade['corte3'] is not None else '-',
            str(grade['final_grade']) if grade['final_grade'] is not None else '-'
        ]
        data.append(row)

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=calificaciones_{course.data[0]['code']}.pdf"}
    )

@api_router.get("/notifications", response_model=List[Notification])
async def get_notifications(current_user: dict = Depends(get_current_user)):
    notifications = supabase.table("notifications").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).limit(100).execute()
    return [Notification(**notif) for notif in notifications.data]

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = supabase.table("notifications").update({"read": True}).eq("id", notification_id).eq("user_id", current_user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    return {"message": "Notificación marcada como leída"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
