from config import HUMANEVAL_LIMIT, MBPP_LIMIT

from run_pipeline import build_parser


def test_run_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])

    assert args.humaneval_limit == HUMANEVAL_LIMIT
    assert args.mbpp_limit == MBPP_LIMIT
    assert args.new_dataset_limit == 0
    assert args.resume is False
    assert args.dry_run is False
    assert args.list_models is False
    assert args.check_data is False
    assert args.diagnose_mbpp is False


def test_run_parser_custom_values():
    parser = build_parser()

    args = parser.parse_args(
        [
            "--humaneval-limit",
            "5",
            "--mbpp-limit",
            "0",
            "--new-dataset-limit",
            "10",
            "--resume",
            "--dry-run",
        ]
    )

    assert args.humaneval_limit == 5
    assert args.mbpp_limit == 0
    assert args.new_dataset_limit == 10
    assert args.resume is True
    assert args.dry_run is True
