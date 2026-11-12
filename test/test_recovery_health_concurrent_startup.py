
import json
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
    inspect_health_lock,
    lock_path_for,
)


PROCESS_COUNT = 6
TIMEOUT = 15


CHILD_CODE = r"""
import json
import sys
import time

from pathlib import Path

from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
    HealthFileAlreadyOwned,
)

health = Path(sys.argv[1])
start = Path(sys.argv[2])
ready = Path(sys.argv[3])
result = Path(sys.argv[4])

ready.write_text("ready", encoding="utf-8")

deadline = time.monotonic() + 15

while not start.exists():
    if time.monotonic() >= deadline:
        sys.exit(4)
    time.sleep(0.005)

owner = RecoveryHealthOwnership(health)

try:
    owner.acquire()

except HealthFileAlreadyOwned:
    result.write_text(
        json.dumps({
            "status": "rejected"
        }),
        encoding="utf-8",
    )
    sys.exit(0)

except Exception as exc:
    result.write_text(
        json.dumps({
            "status": "error",
            "error": repr(exc),
        }),
        encoding="utf-8",
    )
    sys.exit(5)

try:
    result.write_text(
        json.dumps({
            "status": "acquired",
            "token": owner.token,
        }),
        encoding="utf-8",
    )

    # Hold the lock until the parent terminates us.
    time.sleep(60)

finally:
    owner.release()
"""


def wait_until(predicate, timeout=TIMEOUT):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)

    return False


def read_result(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def start_child(health, start, ready, result):
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD_CODE,
            str(health),
            str(start),
            str(ready),
            str(result),
        ],
        cwd=str(Path(__file__).resolve().parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_child(process):
    if process.poll() is None:
        process.kill()

    process.wait(timeout=10)


def main():

    print("RECOVERY HEALTH - CONCURRENT STARTUP")
    print("====================================")

    with tempfile.TemporaryDirectory() as directory:

        root = Path(directory)
        health = root / "health.json"
        start = root / "start"

        processes = []
        result_paths = []

        try:

            # ------------------------------------------
            # Test 1: Prepare six independent processes
            # ------------------------------------------

            for index in range(PROCESS_COUNT):

                ready = root / f"ready-{index}"
                result = root / f"result-{index}.json"

                process = start_child(
                    health,
                    start,
                    ready,
                    result,
                )

                processes.append(process)
                result_paths.append(result)

            def all_ready():
                return all(
                    (root / f"ready-{i}").exists()
                    for i in range(PROCESS_COUNT)
                )

            assert wait_until(all_ready), (
                "Not all child processes became ready."
            )

            assert all(
                p.poll() is None
                for p in processes
            ), "A child exited before the start signal."

            print(
                "TEST 1 - Six independent processes ready: PASSED"
            )

            # ------------------------------------------
            # Test 2: Release processes simultaneously
            # ------------------------------------------

            start.write_text(
                "start",
                encoding="utf-8",
            )

            assert wait_until(
                lambda: all(
                    path.exists()
                    for path in result_paths
                )
            ), "Not all processes published a result."

            results = [
                read_result(path)
                for path in result_paths
            ]

            errors = [
                item
                for item in results
                if item["status"] == "error"
            ]

            assert not errors, (
                f"Unexpected child errors: {errors}"
            )

            print(
                "TEST 2 - Concurrent acquisition attempts completed: PASSED"
            )

            # ------------------------------------------
            # Test 3: Exactly one owner
            # ------------------------------------------

            winners = [
                index
                for index, item in enumerate(results)
                if item["status"] == "acquired"
            ]

            assert len(winners) == 1, (
                f"Expected one owner, got {len(winners)}. "
                f"Results: {results}"
            )

            winner_index = winners[0]
            winner = processes[winner_index]

            assert winner.poll() is None, (
                "Winning process exited unexpectedly."
            )

            print(
                "TEST 3 - Exactly one owner acquired lock: PASSED"
            )

            # ------------------------------------------
            # Test 4: All competing owners rejected
            # ------------------------------------------

            rejected = [
                item
                for item in results
                if item["status"] == "rejected"
            ]

            assert len(rejected) == PROCESS_COUNT - 1, (
                f"Expected {PROCESS_COUNT - 1} rejections, "
                f"got {len(rejected)}."
            )

            print(
                "TEST 4 - Five competing owners rejected: PASSED"
            )

            # ------------------------------------------
            # Test 5: Metadata identifies winner
            # ------------------------------------------

            info = inspect_health_lock(health)

            assert info is not None
            assert info.pid == winner.pid
            assert info.token == results[
                winner_index
            ]["token"]

            print(
                "TEST 5 - Ownership metadata identifies winner: PASSED"
            )

            # ------------------------------------------
            # Test 6: Parent cannot acquire active lock
            # ------------------------------------------

            from application.recovery_health_ownership import (
                HealthFileAlreadyOwned,
            )

            duplicate = RecoveryHealthOwnership(health)

            try:
                duplicate.acquire()

            except HealthFileAlreadyOwned:
                pass

            else:
                duplicate.release()
                raise AssertionError(
                    "Parent acquired an active lock."
                )

            print(
                "TEST 6 - Parent cannot acquire active lock: PASSED"
            )

            # ------------------------------------------
            # Test 7: Kill winning process
            # ------------------------------------------

            stop_child(winner)

            assert winner.poll() is not None

            print(
                "TEST 7 - Winning process forcibly terminated: PASSED"
            )

            # ------------------------------------------
            # Test 8: Persistent lock file survives
            # ------------------------------------------

            assert lock_path_for(health).exists()

            print(
                "TEST 8 - Persistent lock target retained: PASSED"
            )

            # ------------------------------------------
            # Test 9: New owner acquires after crash
            # ------------------------------------------

            with RecoveryHealthOwnership(health) as owner:

                new_info = inspect_health_lock(health)

                assert new_info is not None
                assert new_info.token == owner.token
                assert new_info.pid != winner.pid

            print(
                "TEST 9 - Ownership recovered after crash: PASSED"
            )

            # ------------------------------------------
            # Test 10: Metadata cleanup after release
            # ------------------------------------------

            assert inspect_health_lock(health) is None, (
                "Ownership metadata remained after "
                "normal release."
            )

            print(
                "TEST 10 - Metadata cleaned after release: PASSED"
            )

        finally:

            for process in processes:
                stop_child(process)

    print()
    print("PASS")


if __name__ == "__main__":
    main()
