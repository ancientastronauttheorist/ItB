from src.bridge import writer
from src.model.board import Board, Unit
from src.solver.solver import MechAction


def _board() -> Board:
    board = Board()
    board.units = [
        Unit(
            uid=2,
            type="ExchangeMech",
            x=3,
            y=3,
            hp=2,
            max_hp=2,
            team=1,
            is_mech=True,
            move_speed=3,
            flying=False,
            massive=True,
            armor=False,
            pushable=True,
            weapon="Science_TC_SwapOther",
        )
    ]
    return board


def test_execute_bridge_action_emits_two_click_after_move(monkeypatch):
    commands: list[str] = []

    monkeypatch.setattr(writer, "write_command", commands.append)
    monkeypatch.setattr(writer, "wait_for_ack", lambda timeout=0: "OK")

    action = MechAction(
        mech_uid=2,
        mech_type="ExchangeMech",
        move_to=(5, 3),
        weapon="Science_TC_SwapOther",
        target=(5, 4),
        target2=(6, 2),
        description="Force Swap",
    )

    ack = writer.execute_bridge_action(action, _board())

    assert ack == "OK"
    assert commands == [
        "MOVE 2 5 3",
        "TWO_CLICK_ATTACK 2 0 5 4 6 2",
    ]


def test_attack_mech_two_emits_two_click_command(monkeypatch):
    commands: list[str] = []

    monkeypatch.setattr(writer, "write_command", commands.append)
    monkeypatch.setattr(writer, "wait_for_ack", lambda timeout=0: "OK TWO")

    ack = writer.attack_mech_two(2, 0, 5, 4, 6, 2)

    assert ack == "OK TWO"
    assert commands == ["TWO_CLICK_ATTACK 2 0 5 4 6 2"]
