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
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="시트1(통합 포트폴리오)만 작성하고 종목별 시트는 생략",
    )

    # history 서브커맨드 (D-15): 펀더멘털 트렌드 엑셀 렌더 — main_run.run 과 완전 분리.
    sub = parser.add_subparsers(dest="cmd")
    p_hist = sub.add_parser(
        "history",
        help="펀더멘털 트렌드 엑셀 렌더 (DB → fundamentals_history_*.xlsx)",
        description="펀더멘털 트렌드 엑셀 렌더 (DB → fundamentals_history_*.xlsx)",
    )
    p_hist.add_argument("--tickers", default="tickers.txt")
    p_hist.add_argument("--output-dir", default="output")

    args = parser.parse_args()

    # history 분기: 시트1 흐름(main_run.run)과 분리된 별도 엔트리(D-15).
    if getattr(args, "cmd", None) == "history":
        from stocksig.io.history_render import run_history

        try:
            path = run_history(args.tickers, args.output_dir)
        except SystemExit:
            raise
        except Exception:
            logger.exception("main | history 실행 실패")
            return 1
        # DB 미적재 시 run_history 가 None + 안내 출력 → 깔끔 종료(예외 아님).
        if path is not None:
            print(f"완료: {path}")
        return 0

    # 기본(portfolio) 흐름 — 하위호환. 늦은 import: --help 가 의존성 import 전에 동작.
    from stocksig.main_run import run

    try:
        path = run(
            args.tickers, args.env, args.output_dir, summary_only=args.summary_only
        )
    except SystemExit:
        raise
    except Exception:
        logger.exception("main | 실행 실패")
        return 1

    print(f"완료: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
