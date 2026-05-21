"""Walking Skeleton 엔트리포인트 (EXEC-01/02).

사용 (Windows PowerShell):
    uv run python main.py
    uv run python main.py --tickers tickers.txt --env .env --output-dir output

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
T-01-UTF mitigation: sys.stdout/stderr를 UTF-8로 reconfigure (Windows 콘솔 한국어).
"""

from __future__ import annotations

import argparse
import logging
import sys


# T-01-UTF: Windows 콘솔 한국어 깨짐 방지 (chcp 65001 없이도 동작)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# D-05 한국어 로깅 (encoding=utf-8: 콘솔/파일 모두 안전)
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)

logger = logging.getLogger("main")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="표준편차 기반 주식 매매신호 워크북 생성"
    )
    parser.add_argument(
        "--tickers",
        default="tickers.txt",
        help="티커 목록 파일 경로 (default: tickers.txt)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help=".env 경로 (default: cwd의 .env 자동 탐색)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="출력 디렉터리 (default: output/)",
    )
    args = parser.parse_args()

    # 늦은 import: argparse --help가 의존성 import 전에 동작하도록
    from stocksig.main_run import run

    try:
        path = run(args.tickers, args.env, args.output_dir)
    except SystemExit:
        raise
    except Exception:
        logger.exception("main | 실행 실패")
        return 1

    print(f"완료: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
