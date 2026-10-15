import pytest

from app.classes.helpers.java_memory import read_memory, set_memory

COMMAND = "java -Xms1024M -Xmx2048M -jar server.jar nogui"


def test_read_memory_in_mib():
    assert read_memory(COMMAND) == {"mem_min": 1024, "mem_max": 2048}


def test_read_memory_other_units():
    assert read_memory("java -Xms1G -Xmx4g -jar a.jar") == {
        "mem_min": 1024,
        "mem_max": 4096,
    }


def test_read_memory_missing_flags():
    assert read_memory("./start.sh") == {"mem_min": None, "mem_max": None}


def test_set_memory_changes_only_the_flags():
    assert set_memory(COMMAND, 2048, 4096) == (
        "java -Xms2048M -Xmx4096M -jar server.jar nogui"
    )


def test_set_memory_one_flag():
    assert set_memory(COMMAND, mem_max=3072) == (
        "java -Xms1024M -Xmx3072M -jar server.jar nogui"
    )


def test_set_memory_keeps_quoted_java_path():
    command = '"/opt/java 21/bin/java" -Xms1G -Xmx2G -jar server.jar'
    assert set_memory(command, mem_max=4096) == (
        '"/opt/java 21/bin/java" -Xms1024M -Xmx4096M -jar server.jar'
    )


def test_set_memory_ignores_lookalike_text():
    command = "java -Xms1G -Xmx2G -jar server-Xmx9G.jar"
    assert set_memory(command, mem_max=4096).endswith("server-Xmx9G.jar")


@pytest.mark.parametrize(
    "mem_min, mem_max",
    [(4096, 2048), (64, None), (None, 10**9), ("2G", None), (True, None)],
)
def test_set_memory_rejects_bad_values(mem_min, mem_max):
    with pytest.raises(ValueError):
        set_memory(COMMAND, mem_min, mem_max)


def test_set_memory_needs_the_flag():
    with pytest.raises(ValueError):
        set_memory("java -jar server.jar", mem_max=2048)
