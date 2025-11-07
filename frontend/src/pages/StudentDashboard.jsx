import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { api } from "@/App";
import { GraduationCap, Plus, BookOpen, Award, Bell, LogOut, Loader2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function StudentDashboard({ user, setUser }) {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [grade, setGrade] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false);
  const [accessCode, setAccessCode] = useState("");

  useEffect(() => {
    loadCourses();
    loadNotifications();
  }, []);

  useEffect(() => {
    if (selectedCourse) {
      loadGrade(selectedCourse.id);
    }
  }, [selectedCourse]);

  const loadCourses = async () => {
    try {
      const response = await api.get("/courses/student");
      setCourses(response.data);
    } catch (error) {
      toast.error("Error al cargar cursos");
    }
  };

  const loadGrade = async (courseId) => {
    try {
      const response = await api.get(`/grades/student/course/${courseId}`);
      setGrade(response.data);
    } catch (error) {
      console.error("Error loading grade");
      setGrade(null);
    }
  };

  const loadNotifications = async () => {
    try {
      const response = await api.get("/notifications");
      setNotifications(response.data);
    } catch (error) {
      console.error("Error loading notifications");
    }
  };

  const handleEnroll = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await api.post("/courses/enroll", { access_code: accessCode });
      toast.success("Inscripción exitosa");
      setEnrollDialogOpen(false);
      setAccessCode("");
      loadCourses();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al inscribirse");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setUser(null);
    navigate("/");
    toast.success("Sesión cerrada");
  };

  const markNotificationRead = async (notificationId) => {
    try {
      await api.put(`/notifications/${notificationId}/read`);
      loadNotifications();
    } catch (error) {
      console.error("Error marking notification as read");
    }
  };

  const calculateProgress = (corte1, corte2, corte3) => {
    let completed = 0;
    if (corte1 !== null) completed += 33.33;
    if (corte2 !== null) completed += 33.33;
    if (corte3 !== null) completed += 33.34;
    return Math.round(completed);
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-emerald-50">
      {/* Navbar */}
      <nav className="border-b bg-white/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <GraduationCap className="h-8 w-8 text-blue-600" />
              <span className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-emerald-600 bg-clip-text text-transparent" style={{fontFamily: 'Space Grotesk, sans-serif'}}>AcademiCO</span>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">Estudiante: <span className="font-semibold">{user.full_name}</span></span>
              <Button variant="ghost" size="sm" className="relative" data-testid="notifications-btn">
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <Badge className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs" data-testid="notification-badge">
                    {unreadCount}
                  </Badge>
                )}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleLogout} data-testid="logout-btn">
                <LogOut className="h-5 w-5 mr-2" />
                Salir
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Tabs defaultValue="courses" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 max-w-lg">
            <TabsTrigger value="courses" data-testid="courses-tab">Mis Cursos</TabsTrigger>
            <TabsTrigger value="grades" data-testid="grades-tab">Calificaciones</TabsTrigger>
            <TabsTrigger value="notifications" data-testid="notifications-tab">Notificaciones</TabsTrigger>
          </TabsList>

          {/* Courses Tab */}
          <TabsContent value="courses" className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-900" style={{fontFamily: 'Space Grotesk, sans-serif'}}>Mis Cursos</h1>
                <p className="text-gray-600 mt-1">Cursos en los que estás inscrito</p>
              </div>
              <Dialog open={enrollDialogOpen} onOpenChange={setEnrollDialogOpen}>
                <DialogTrigger asChild>
                  <Button data-testid="enroll-course-btn">
                    <Plus className="mr-2 h-4 w-4" />
                    Inscribirse a Curso
                  </Button>
                </DialogTrigger>
                <DialogContent data-testid="enroll-dialog">
                  <DialogHeader>
                    <DialogTitle>Inscribirse a un Curso</DialogTitle>
                    <DialogDescription>Ingresa el código de acceso proporcionado por tu docente</DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleEnroll} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="access_code">Código de Acceso</Label>
                      <Input
                        id="access_code"
                        placeholder="Ej: abc123xyz"
                        value={accessCode}
                        onChange={(e) => setAccessCode(e.target.value)}
                        required
                        data-testid="access-code-input"
                      />
                    </div>
                    <div className="flex space-x-2">
                      <Button type="submit" disabled={loading} data-testid="submit-enroll-btn">
                        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                        Inscribirse
                      </Button>
                      <Button type="button" variant="outline" onClick={() => setEnrollDialogOpen(false)} data-testid="cancel-enroll-btn">
                        Cancelar
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {courses.map((course) => (
                <Card
                  key={course.id}
                  className="hover:shadow-lg transition-shadow cursor-pointer"
                  onClick={() => setSelectedCourse(course)}
                  data-testid={`course-card-${course.code}`}
                >
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <BookOpen className="h-5 w-5 text-blue-600" />
                      <span>{course.name}</span>
                    </CardTitle>
                    <CardDescription>
                      <Badge variant="outline" className="mt-2">{course.code}</Badge>
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm">
                      <p className="text-gray-600">{course.description}</p>
                      <p className="text-gray-600"><span className="font-semibold">Período:</span> {course.academic_period}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {courses.length === 0 && (
              <Card className="text-center py-12" data-testid="no-courses-message">
                <CardContent>
                  <BookOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No estás inscrito en ningún curso</p>
                  <p className="text-sm text-gray-500 mt-2">Solicita el código de acceso a tu docente para inscribirte</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Grades Tab */}
          <TabsContent value="grades" className="space-y-6">
            {selectedCourse ? (
              <>
                <div>
                  <h1 className="text-3xl font-bold text-gray-900" style={{fontFamily: 'Space Grotesk, sans-serif'}}>{selectedCourse.name}</h1>
                  <p className="text-gray-600 mt-1">{selectedCourse.code} - {selectedCourse.academic_period}</p>
                </div>

                {grade ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Grades Card */}
                    <Card data-testid="grades-card">
                      <CardHeader>
                        <CardTitle className="flex items-center">
                          <Award className="mr-2 h-5 w-5" />
                          Calificaciones por Cortes
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="space-y-2">
                          <div className="flex justify-between items-center">
                            <span className="font-semibold">Corte 1 (30%)</span>
                            <Badge variant={grade.corte1 !== null ? "default" : "outline"} data-testid="corte1-badge">
                              {grade.corte1 !== null ? grade.corte1 : "Pendiente"}
                            </Badge>
                          </div>
                          <Progress value={grade.corte1 !== null ? 100 : 0} className="h-2" />
                        </div>

                        <div className="space-y-2">
                          <div className="flex justify-between items-center">
                            <span className="font-semibold">Corte 2 (35%)</span>
                            <Badge variant={grade.corte2 !== null ? "default" : "outline"} data-testid="corte2-badge">
                              {grade.corte2 !== null ? grade.corte2 : "Pendiente"}
                            </Badge>
                          </div>
                          <Progress value={grade.corte2 !== null ? 100 : 0} className="h-2" />
                        </div>

                        <div className="space-y-2">
                          <div className="flex justify-between items-center">
                            <span className="font-semibold">Corte 3 (35%)</span>
                            <Badge variant={grade.corte3 !== null ? "default" : "outline"} data-testid="corte3-badge">
                              {grade.corte3 !== null ? grade.corte3 : "Pendiente"}
                            </Badge>
                          </div>
                          <Progress value={grade.corte3 !== null ? 100 : 0} className="h-2" />
                        </div>

                        <div className="pt-4 border-t">
                          <div className="flex justify-between items-center">
                            <span className="text-lg font-bold">Nota Final</span>
                            {grade.final_grade !== null ? (
                              <Badge
                                variant={grade.final_grade >= 3.0 ? "default" : "destructive"}
                                className="text-lg px-4 py-1"
                                data-testid="final-grade-badge"
                              >
                                {grade.final_grade}
                              </Badge>
                            ) : (
                              <Badge variant="outline" data-testid="final-grade-pending">Pendiente</Badge>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Progress Card */}
                    <Card data-testid="progress-card">
                      <CardHeader>
                        <CardTitle>Progreso del Curso</CardTitle>
                        <CardDescription>Calificaciones completadas</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="text-center">
                          <div className="text-5xl font-bold text-blue-600 mb-2">
                            {calculateProgress(grade.corte1, grade.corte2, grade.corte3)}%
                          </div>
                          <Progress
                            value={calculateProgress(grade.corte1, grade.corte2, grade.corte3)}
                            className="h-4 mb-4"
                          />
                        </div>

                        <div className="space-y-2 text-sm">
                          <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                            <span>Cortes evaluados:</span>
                            <span className="font-semibold">
                              {[grade.corte1, grade.corte2, grade.corte3].filter(c => c !== null).length} de 3
                            </span>
                          </div>
                          <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                            <span>Estado:</span>
                            <Badge variant={grade.final_grade !== null ? "default" : "outline"}>
                              {grade.final_grade !== null ? "Completo" : "En Progreso"}
                            </Badge>
                          </div>
                          {grade.final_grade !== null && (
                            <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                              <span>Resultado:</span>
                              <Badge variant={grade.final_grade >= 3.0 ? "default" : "destructive"}>
                                {grade.final_grade >= 3.0 ? "Aprobado" : "Reprobado"}
                              </Badge>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <Card className="text-center py-12" data-testid="no-grades-message">
                    <CardContent>
                      <Award className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-600">No hay calificaciones disponibles para este curso</p>
                    </CardContent>
                  </Card>
                )}
              </>
            ) : (
              <Card className="text-center py-12" data-testid="select-course-message">
                <CardContent>
                  <BookOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">Selecciona un curso de la pestaña "Mis Cursos" para ver tus calificaciones</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Notifications Tab */}
          <TabsContent value="notifications" className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900" style={{fontFamily: 'Space Grotesk, sans-serif'}}>Notificaciones</h1>
              <p className="text-gray-600 mt-1">Mantente al día con tus calificaciones</p>
            </div>

            <div className="space-y-4">
              {notifications.length > 0 ? (
                notifications.map((notification) => (
                  <Card
                    key={notification.id}
                    className={`cursor-pointer hover:shadow-md transition-shadow ${!notification.read ? 'border-blue-500' : ''}`}
                    onClick={() => markNotificationRead(notification.id)}
                    data-testid={`notification-${notification.id}`}
                  >
                    <CardContent className="flex items-start justify-between p-4">
                      <div className="flex items-start space-x-4 flex-1">
                        <div className={`w-2 h-2 rounded-full mt-2 ${!notification.read ? 'bg-blue-500' : 'bg-gray-300'}`}></div>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{notification.message}</p>
                          <p className="text-sm text-gray-500 mt-1">
                            {new Date(notification.created_at).toLocaleDateString('es-CO', {
                              year: 'numeric',
                              month: 'long',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </p>
                        </div>
                      </div>
                      {!notification.read && (
                        <Badge variant="default" data-testid="unread-badge">Nueva</Badge>
                      )}
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Card className="text-center py-12" data-testid="no-notifications-message">
                  <CardContent>
                    <Bell className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No tienes notificaciones</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}