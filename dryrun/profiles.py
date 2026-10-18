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
    inputs: dict[str, str] = field(default_factory=dict)  # file the student brings -> sample file in examples/


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


# For terminal labs extracted from slides (lesson.sh), e.g. the video -> COLMAP 3D reconstruction class.
# Each student brings their own video, the way it happened in the real class.
VIDEO = "examples/recon3d/input.mp4"        # 1080p, 18 s
VIDEO_4K = "examples/recon3d/input_4k.mp4"  # 2160p, 18 s

SHELL_PROFILES = [
    Profile(
        id="teacher",
        name="선생님 PC",
        description="The teacher's Ubuntu PC: ffmpeg installed, a 1080p phone video named input.mp4.",
        is_teacher=True,
        inputs={"input.mp4": VIDEO},
    ),
    Profile(
        id="noffmpeg",
        name="ffmpeg 없는 학교 PC",
        description="A school PC where ffmpeg was never installed. The student types the commands exactly as on the slide.",
        setup=["sudo dpkg -r --force-depends ffmpeg >/dev/null 2>&1"],
        inputs={"input.mp4": VIDEO},
    ),
    Profile(
        id="phone4k",
        name="4K로 촬영한 학생",
        description="Filmed with a newer phone in 4K (3840x2160), so every extracted frame is 4K. The next step, COLMAP dense stereo, is the most memory-hungry step.",
        inputs={"input.mp4": VIDEO_4K},
    ),
    Profile(
        id="iphone",
        name="아이폰으로 찍은 학생",
        description="An iPhone video keeps its original name IMG_0412.MOV instead of input.mp4.",
        inputs={"IMG_0412.MOV": VIDEO},
    ),
]


def profiles_for(files: dict) -> list[Profile]:
    return SHELL_PROFILES if "lesson.sh" in files else PROFILES
