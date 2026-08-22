from topology.help import SUBCOMMANDS, build_help_text, main


def test_build_help_text_includes_usage_line():
    text = build_help_text()
    assert 'Usage: /load-topology [subcommand]' in text


def test_build_help_text_includes_every_subcommand_and_description():
    text = build_help_text()
    for usage, description in SUBCOMMANDS:
        assert usage in text
        assert description in text


def test_build_help_text_lists_help_itself():
    text = build_help_text()
    assert 'help' in text
    assert 'Show this help message.' in text


def test_main_prints_help_text_to_stdout(capsys):
    main()
    captured = capsys.readouterr()
    assert captured.out.strip() == build_help_text()
