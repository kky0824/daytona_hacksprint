"""Student machine profiles to rehearse a lab on."""
from dataclasses import dataclass, field


@dataclass
class Profile:
    id: str
    name: str            # shown in the UI
    description: str     # what kind of student this is; also given to the LLM
    image: str | None = None  # None = Daytona's default snapshot (Python with common packages)
    setup: list[str] = field(default_factory=list)  # run inside the lab folder before the lesson
    run_from_home: bool = False  # run `python lab/lesson.py` from the home folder instead of the lab folder
    python: str = "python"  # interpreter used to run the lesson
    is_teacher: bool = False


PROFILES = [
    Profile(
        id="teacher",
        name="선생님 PC",
        description="The teacher's machine. Packages were installed months ago and the lab works here.",
        is_teacher=True,
    ),
    Profile(
        id="fresh",
        name="새 PC 학생",
        description="A brand-new PC with only Python. Installs exactly what requirements.txt lists, nothing else.",
        # A clean virtualenv on the default snapshot: same effect as a bare image, but starts in seconds.
        setup=["python -m venv /tmp/fresh", "/tmp/fresh/bin/pip install -q -r requirements.txt"],
        python="/tmp/fresh/bin/python",
    ),
    Profile(
        id="desktop",
        name="바탕화면에서 실행한 학생",
        description="Same packages as the teacher, but runs the script from another folder: python lab/lesson.py.",
        run_from_home=True,
    ),
    Profile(
        id="today",
        name="오늘 설치한 학생",
        description="Ran `pip install -U -r requirements.txt` today, so gets the newest version of every package.",
        setup=["pip install -q -U -r requirements.txt"],
    ),
]
