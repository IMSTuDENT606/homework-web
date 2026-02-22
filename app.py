from flask import Flask, render_template, request , redirect, url_for , session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_file
ALLOWED_EXT = {"pdf", "docx","jpg", "png"}

app = Flask(__name__)
app.secret_key = "my_secret_key"

import json
import os
from datetime import datetime

TASK_FILE = "tasks.json"

def load_tasks():
    if not os.path.exists(TASK_FILE):
        return []
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

STUDENT_FILE = "students.json"

def load_students():
    if not os.path.exists(STUDENT_FILE):
        return []

    if os.path.getsize(STUDENT_FILE) == 0:
        return []

    with open(STUDENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    
from werkzeug.security import generate_password_hash, check_password_hash

USER_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        return []
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

ALL_STUDENTS = ["student1", "student2", "student3"]

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        students = load_students()

        # ตรวจว่ามี user ไหม
        for s in students:

            if not isinstance(s, dict):
                continue

            if (
                s.get("username") == username
                and check_password_hash(s.get("password", ""), password)
                and s.get("role") == role
            ):

                # ✅ เจอ user
                session["username"] = username
                session["role"] = role

                if role == "student":
                    return redirect(url_for("student_home"))
                else:
                    return redirect(url_for("teacher_home"))

        # ❌ ไม่เจอ
        return render_template(
            "login.html",
            error="ไม่พบผู้ใช้ หรือรหัสผ่านผิด"
        )

    return render_template("login.html")

from datetime import datetime

@app.route("/student")
def student_home():
    if session.get("role") != "student":
        return redirect("/")

    tasks = load_tasks()
    now = datetime.now()
    view_tasks = []

    total = 0
    checked = 0
    pending = 0
    sum_score = 0
    score_count = 0

    username = session["username"]

    for t in tasks:

        deadline = datetime.strptime(t["deadline"], "%Y-%m-%dT%H:%M")
        diff = deadline - now
        seconds_left = int(diff.total_seconds())

        submitted_map = t.get("submitted_by", {})
        data = submitted_map.get(username)

        score = None
        comment = ""
        status_check = None
        submit_time = None

    # ===== ดึงข้อมูลการส่ง =====
        if isinstance(data, dict):
            submit_time = data.get("time")
            score = data.get("score")
            comment = data.get("comment")
            status_check = data.get("status", "pending")

        elif isinstance(data, str):
            submit_time = data


    # ===== คำนวณ status =====
        if submit_time:
            submit_dt = datetime.strptime(submit_time, "%Y-%m-%d %H:%M:%S")

            if submit_dt > deadline:
                status = "submitted_late"
            else:
                status = "submitted"

        elif now > deadline:
            status = "late"
            seconds_left = 0

        else:
            status = "pending"


    # ===== คำนวณ alert (ย้ายมาหลังสุด) =====
        alert = None

        if status == "pending" and seconds_left <= 86400:
            alert = "near_deadline"

        elif status == "late":
            alert = "overdue"

        elif status_check == "checked":
            alert = "checked"

        elif score is not None and score >= 80:
            alert = "excellent"


    # ===== นับสถิติ =====
        total += 1

        if status_check == "checked":
            checked += 1

            if score is not None:
                sum_score += score
                score_count += 1

        else:
            if submit_time:
                pending += 1


    # ===== ส่งเข้า template =====
        view_tasks.append({
            **t,
            "seconds_left": seconds_left,
            "view_status": status,
            "score": score,
            "comment": comment,
            "check_status": status_check,
            "alert": alert
        })

    avg = round(sum_score / score_count, 2) if score_count > 0 else 0

    return render_template(
        "student_home.html",
        username=session["username"],
        tasks=view_tasks,
        total=total,
        checked=checked,
        pending=pending,
        avg=avg
    )

@app.route("/teacher", methods=["GET", "POST"])
def teacher_home():
    if session.get("role") != "teacher":
        return redirect("/")

    tasks = load_tasks()
    students = load_students()
    now = datetime.now()

    # ===== สร้างงานใหม่ =====
    if request.method == "POST":
        subject = request.form["subject"]
        title = request.form["title"]
        deadline = request.form["deadline"]

        new_id = max([t["id"] for t in tasks], default=0) + 1

        tasks.append({
            "id": new_id,
            "subject": subject,
            "title": title,
            "deadline": deadline,
            "submitted_by": {},
            "files": {}
        })

        save_tasks(tasks)
        return redirect("/teacher")

    # ===== คำนวณสถานะทุกงาน =====
    for t in tasks:

        deadline = datetime.strptime(t["deadline"], "%Y-%m-%dT%H:%M")
        submitted = t.get("submitted_by", {})

        total = len(students)
        submitted_count = len(submitted)

        if submitted_count == 0 and now < deadline:
            t["view_status"] = "pending"

        elif submitted_count == 0 and now > deadline:
            t["view_status"] = "late"

        elif submitted_count == total:
            late = False

            for data in submitted.values():

                if isinstance(data, dict):
                    time_str = data.get("time")
                else:
                    time_str = data

                if not time_str:
                    continue

                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

                if dt > deadline:
                    late = True
                    break

            if late:
                t["view_status"] = "submitted_late"
            else:
                t["view_status"] = "submitted"

        else:
            t["view_status"] = "partial"

    return render_template("teacher_home.html", tasks=tasks)

@app.route("/task/<int:task_id>")
def task_detail(task_id):
    tasks = load_tasks()
    students = load_students()

    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return "Task not found", 404

    # ✅ กันพัง: ถ้าไม่มี files ให้เป็น dict ว่าง
    task.setdefault("files", {})

    submitted = task.get("submitted_by", {})
    deadline = datetime.strptime(task["deadline"], "%Y-%m-%dT%H:%M")

    # แยกตรงเวลา / ช้า
    late_students = []
    on_time_students = []

    for student, data in submitted.items():

        if not isinstance(data, dict):
            continue

        submit_time = data.get("time")
        if not submit_time:
            continue

        submit_dt = datetime.strptime(submit_time, "%Y-%m-%d %H:%M:%S")

        student_data = {
            "name": student,
            "time": submit_time,
            "score": data.get("score"),
            "comment": data.get("comment"),
            "status": data.get("status", "pending")
        }

        if submit_dt > deadline:
            late_students.append(student_data)
        else:
            on_time_students.append(student_data)

    student_names = [s["username"] for s in students]

    not_submitted = [
        name for name in student_names
        if name not in submitted
    ]

    return render_template(
        "task_detail.html",
        task=task,
        submitted=on_time_students,
        late=late_students,
        not_submitted=not_submitted
    )

from datetime import datetime

@app.route("/create_work", methods=["GET", "POST"])
def create_work():
    if session.get("role") != "teacher":
        return redirect("/")
    
    if request.method == "POST":
        subject = request.form["subject"]
        title = request.form["title"]
        deadline = request.form["deadline"]

        tasks = load_tasks()
        students = load_students()
        new_id = max([t["id"] for t in tasks], default=0) + 1

        tasks.append({
            "id": new_id,
            "subject": subject,
            "title": title,
            "status": "pending",
            "deadline": deadline,
            "submitted_by": {},
            "files": {}
        })

        save_tasks(tasks)
        return redirect(url_for("teacher_home"))

    return render_template("create_work.html")

@app.route("/delete/<int:task_id>")
def delete_task(task_id):
    if session.get("role") != "teacher":
        return redirect("/")
    
    tasks = load_tasks()
    tasks = [t for t in tasks if t['id'] != task_id]
    save_tasks(tasks)
    
    return redirect("/teacher_home")

from werkzeug.utils import secure_filename

@app.route("/submit_work/<int:task_id>", methods=["POST"])
def submit_work(task_id):
    if session.get("role") != "student":
        return redirect("/")

    username = session["username"]
    tasks = load_tasks()
    file = request.files.get("file")

    now = datetime.now()  # ✅ ใช้ได้แล้ว

    for t in tasks:
        if t["id"] == task_id:

            deadline = datetime.strptime(t["deadline"], "%Y-%m-%dT%H:%M")

            if not isinstance(t.get("submitted_by"), dict):
                t["submitted_by"] = {}

            t["submitted_by"][username] = {
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "score": None,
                "comment": "",
                "status": "pending"
            }

            if file and file.filename != "":
                if file and file.filename != "":

                    ext = file.filename.rsplit(".", 1)[1].lower()

                    if ext not in ALLOWED_EXT:
                        return "ไฟล์ชนิดนี้ไม่อนุญาต"

                task_folder = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    f"task_{task_id}"
                )
                os.makedirs(task_folder, exist_ok=True)

                filename = secure_filename(f"{username}.{ext}")
                filepath = os.path.join(task_folder, filename)
                file.save(filepath)

                t.setdefault("files", {})
                t["files"][username] = filename
            else:
                t.setdefault("files", {})
                t["files"].pop(username, None)

            break

    save_tasks(tasks)
    return redirect(url_for("student_home"))

@app.route("/grade/<int:task_id>/<student>", methods=["POST"])
def grade(task_id, student):

    if session.get("role") != "teacher":
        return redirect("/")
    
    tasks = load_tasks()
    score = request.form.get("score")

    if not score:
        return "กรุณาใส่คะแนน"

    score = int(score)

    if score < 0 or score > 100:
        return "คะแนนต้องอยู่ระหว่าง 0-100"
    
    comment = request.form["comment"]

    for t in tasks:
        if t["id"] == task_id:
            if student in t["submitted_by"] and isinstance(t["submitted_by"][student], dict):
                t["submitted_by"][student]["score"] = int(score)
                t["submitted_by"][student]["comment"] = comment
                t["submitted_by"][student]["status"] = "checked"

    save_tasks(tasks)
    return redirect(f"/task/{task_id}")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/mywork")
def mywork():
    return render_template("mywork.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

from flask import send_from_directory

@app.route("/download/<int:task_id>/<filename>")
def download_file(task_id, filename):
    if session.get("role") != "teacher":
        return redirect("/")
    
    folder = os.path.join(app.config["UPLOAD_FOLDER"], f"task_{task_id}")
    return send_from_directory(folder, filename, as_attachment=True)

@app.route("/mark_checked", methods=["POST"])
def mark_checked():

    if session.get("role") != "teacher":
        return redirect("/")

    task_id = int(request.form["task_id"])
    username = request.form["username"]

    tasks = load_tasks()   # ✅ ใช้ function เดิม

    for t in tasks:
        if t["id"] == task_id:
            if username in t["submitted_by"]:
                if isinstance(t["submitted_by"][username], dict):
                    t["submitted_by"][username]["status"] = "checked"

    save_tasks(tasks)      # ✅ save ถูกไฟล์แน่นอน

    return redirect(f"/task/{task_id}")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        students = load_students()

        for s in students:

    # กันกรณีเป็น string เก่า
            if isinstance(s, str):
                continue

            if s.get("username") == username:
                return "Username นี้ถูกใช้แล้ว"

        students.append({
            "username": username,
            "password": generate_password_hash(password),
            "role": role
        })

        with open(STUDENT_FILE, "w", encoding="utf-8") as f:
            json.dump(students, f, ensure_ascii=False, indent=2)

        return redirect("/")

    return render_template("register.html")

from openpyxl import Workbook

@app.route("/export_excel")
def export_excel():

    if session.get("role") != "teacher":
        return redirect("/")

    tasks = load_tasks()
    students = load_students()

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"

    # Header
    ws.append([
        "ชื่อผู้เรียน",
        "งาน",
        "วิชา",
        "คะแนน",
        "สถานะ",
        "กำหนดส่ง"
    ])

    for t in tasks:

        submitted = t.get("submitted_by", {})

        for s in students:

            username = s["username"]   # ✅ จุดสำคัญ

            data = submitted.get(username)

            score = "-"
            status = "ยังไม่ส่ง"

            if isinstance(data, dict):

                score = data.get("score", "-")

                if data.get("status") == "checked":
                    status = "ตรวจแล้ว"
                else:
                    status = "รอตรวจ"

            ws.append([
                username,
                t["title"],
                t["subject"],
                score,
                status,
                t["deadline"]
            ])

    file_path = "report.xlsx"
    wb.save(file_path)

    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)