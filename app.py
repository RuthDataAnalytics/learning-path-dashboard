import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(page_title="Customised Learning Path", layout="wide")
HERE = Path(__file__).parent
SUBJECTS = ["English", "Maths", "Science", "Social"]


@st.cache_data
def load_all():
    data = pd.read_csv(HERE / "students_risk.csv")
    data["Weak_Subjects"] = data["Weak_Subjects"].fillna("None")
    plan = pd.read_csv(HERE / "batch_assignments.csv")
    summary = pd.read_csv(HERE / "batch_summary.csv")
    teacher_load = pd.read_csv(HERE / "teacher_load.csv")
    impact = pd.read_csv(HERE / "impact_results.csv")
    return data, plan, summary, teacher_load, impact


data, plan, summary, teacher_load, impact = load_all()


def marks_figure(student, class_avg):
    x = np.arange(len(SUBJECTS))
    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.bar(x - 0.2, [student[s] for s in SUBJECTS], 0.4, label="Student", color="#0E6B7A")
    ax.bar(x + 0.2, class_avg.values, 0.4, label="Class average", color="#BBBBBB")
    ax.set_xticks(x)
    ax.set_xticklabels(SUBJECTS)
    ax.set_ylim(0, 100)
    ax.legend()
    ax.set_title("PT1 marks vs class average")
    fig.tight_layout()
    return fig


def report_pdf(student_id):
    s = data[data.Student_ID == student_id].iloc[0]
    my_plan = plan[plan.Student_ID == student_id].sort_values("Priority")
    avg = data[data.Class == s["Class"]][SUBJECTS].mean()
    styles = getSampleStyleSheet()

    fig = marks_figure(s, avg)
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", dpi=120)
    plt.close(fig)
    img_buf.seek(0)

    rows = [["Subject", "PT1 marks", "Class average", "Status"]]
    for sub in SUBJECTS:
        rows.append([sub, int(s[sub]), round(avg[sub], 1), s[sub + "_Status"]])
    t1 = Table(rows, colWidths=[4 * cm, 3 * cm, 3.5 * cm, 3 * cm])
    st_style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8EC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]
    for i, sub in enumerate(SUBJECTS, 1):
        if s[sub + "_Status"] == "Weak":
            st_style.append(("TEXTCOLOR", (3, i), (3, i), colors.red))
    t1.setStyle(TableStyle(st_style))

    best = max(SUBJECTS, key=lambda x: s[x])
    el = [Paragraph("Personalised Learning Report", styles["Title"]),
          Paragraph(f"Student: {student_id} | School: {s['School_ID']} | Class: {s['Class']}", styles["Normal"]),
          Paragraph(f"Learner profile: {s['Profile']}", styles["Normal"]), Spacer(1, 10), t1, Spacer(1, 8),
          Image(img_buf, width=14 * cm, height=6.5 * cm),
          Paragraph(f"<b>Strongest subject:</b> {best}. <b>Predicted PT2 risk:</b> "
                    f"{s['Risk_Level']} ({s['Risk_Probability']}%)", styles["Normal"]),
          Spacer(1, 10), Paragraph("Study plan", styles["Heading2"])]
    if len(my_plan) == 0:
        el.append(Paragraph("No extra classes needed. Keep up the good work!", styles["Normal"]))
    else:
        rows = [["Priority", "Subject", "Sessions/week", "Weeks", "Batch", "Teacher"]]
        for _, r in my_plan.iterrows():
            rows.append([r["Priority"], r["Subject"], r["Sessions_Per_Week"], r["Weeks"], r["Batch_ID"], r["Teacher_ID"]])
        t2 = Table(rows)
        t2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8EC")),
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        el.append(t2)
    el += [Spacer(1, 12), Paragraph("<i>Prepared from simulated data. This report is guidance to support "
                                    "the student, not a judgement.</i>", styles["Normal"])]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4, topMargin=1.5 * cm).build(el)
    return out.getvalue()


# ---------- Sidebar: school, then class ----------
st.sidebar.title("Learning Path")
school = st.sidebar.selectbox("School", sorted(data.School_ID.unique()))
school_data = data[data.School_ID == school]
cls = st.sidebar.selectbox("Class", sorted(school_data.Class.unique()))
class_data = school_data[school_data.Class == cls]
st.sidebar.caption("This demo uses simulated student data.")

st.title(f"{school}  |  Class {cls}")
tab_over, tab_students, tab_report, tab_batches, tab_impact = st.tabs(
    ["Overview", "Students", "Student report", "Batches and teachers", "Impact"])

# ---------- Overview ----------
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", len(class_data))
    c2.metric("Weak in at least one subject", int((class_data.Weak_Count > 0).sum()))
    c3.metric("High PT2 risk", int((class_data.Risk_Level == "High").sum()))
    c4.metric("Average PT1 marks", round(class_data.Average.mean(), 1))

    left, right = st.columns(2)
    with left:
        st.subheader("Weak students by subject")
        weak_counts = pd.Series({s: int((class_data[s + "_Status"] == "Weak").sum()) for s in SUBJECTS})
        st.bar_chart(weak_counts)
    with right:
        st.subheader("Learner profiles")
        st.bar_chart(class_data.Profile.value_counts())

    st.subheader(f"{school}: students needing support, by class")
    by_class = school_data.groupby("Class").apply(lambda g: round((g.Weak_Count > 0).mean() * 100, 1))
    st.bar_chart(by_class.rename("% weak in at least one subject"))

# ---------- Students ----------
with tab_students:
    only_weak = st.checkbox("Show only weak students")
    levels = st.multiselect("Risk level", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    view = class_data[class_data.Risk_Level.isin(levels)]
    if only_weak:
        view = view[view.Weak_Count > 0]
    st.write(f"{len(view)} students")
    cols = ["Student_ID", "Attendance"] + SUBJECTS + ["Average", "Weak_Subjects", "Profile", "Risk_Level"]
    st.dataframe(view[cols].reset_index(drop=True), width="stretch")

# ---------- Student report ----------
with tab_report:
    sid = st.selectbox("Student", class_data.Student_ID.tolist())
    s = class_data[class_data.Student_ID == sid].iloc[0]
    avg = class_data[SUBJECTS].mean()
    a, b, c = st.columns(3)
    a.metric("Profile", s["Profile"])
    b.metric("PT2 risk", f"{s['Risk_Level']} ({s['Risk_Probability']}%)")
    c.metric("Weak subjects", s["Weak_Subjects"])
    st.pyplot(marks_figure(s, avg))
    st.subheader("Study plan")
    my_plan = plan[plan.Student_ID == sid].sort_values("Priority")
    if len(my_plan) == 0:
        st.success("No extra classes needed.")
    else:
        st.dataframe(my_plan[["Priority", "Subject", "PT1_Marks", "Reason", "Sessions_Per_Week",
                              "Weeks", "Batch_ID", "Teacher_ID"]].reset_index(drop=True),
                     width="stretch")
    st.download_button("Download PDF report", data=report_pdf(sid), file_name=f"{sid}.pdf",
                       mime="application/pdf")

# ---------- Batches and teachers ----------
with tab_batches:
    school_batches = summary[summary.School_ID == school]
    st.subheader("Extra-class batches")
    st.dataframe(school_batches.reset_index(drop=True), width="stretch")
    if len(school_batches):
        batch = st.selectbox("See the students in a batch", school_batches.Batch_ID.tolist())
        st.dataframe(plan[plan.Batch_ID == batch][["Student_ID", "Class", "Subject", "PT1_Marks",
                                                    "Priority", "Sessions_Per_Week", "Weeks"]]
                     .reset_index(drop=True), width="stretch")
    st.subheader("Teacher workload")
    st.dataframe(teacher_load[teacher_load.Teacher_ID.isin(school_batches.Teacher_ID)]
                 .reset_index(drop=True), width="stretch")

# ---------- Impact ----------
with tab_impact:
    st.info("PT2 and the effect of extra classes are simulated in this demo. "
            "This page shows how the evaluation works; it is not real evidence.")
    below = impact[impact.PT1_Marks < 40]
    m1, m2, m3 = st.columns(3)
    m1.metric("Average gain from extra classes", f"{impact.Gain.mean():.1f} marks")
    m2.metric("Below 40 in PT1", len(below))
    m3.metric("Crossed 40 with extra classes",
              f"{int((below.PT2_With_Extra >= 40).sum())} (vs {int((below.PT2_Without_Extra >= 40).sum())} without)")
    st.bar_chart(impact.groupby("Subject")[["PT1_Marks", "PT2_Without_Extra", "PT2_With_Extra"]].mean())
