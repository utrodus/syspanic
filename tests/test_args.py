import pytest

from syspanic.app import build_parser


def test_demo_flag_defaults_off():
    args = build_parser().parse_args([])
    assert args.demo is False


def test_demo_flag_parses():
    args = build_parser().parse_args(["--demo"])
    assert args.demo is True


def test_version_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert "SysPanic 0.1.0" in capsys.readouterr().out
