"""Komut satırı arayüzü: fetch, compute, report, site, all."""

import argparse
import io
import logging
import sys
import time

from fantasy9cat import config

logger = logging.getLogger("fantasy9cat.cli")

EXIT_OK = 0
EXIT_ERROR = 1


def _cmd_fetch(args: argparse.Namespace) -> int:
    """Ham veriyi çeker; hata durumunda Türkçe mesaj basar ve 1 döner."""
    from fantasy9cat import fetch

    try:
        n = fetch.run_fetch(args.season)
    except fetch.FetchError as exc:
        print(f"Hata: Veri çekilemedi. {exc}", file=sys.stderr)
        return EXIT_ERROR
    except fetch.DataValidationError as exc:
        print(f"Hata: Veri doğrulama başarısız. {exc}", file=sys.stderr)
        return EXIT_ERROR
    except FileExistsError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"{n} oyuncu yazıldı: {config.raw_csv_path(args.season)}")
    return EXIT_OK


def _cmd_compute(args: argparse.Namespace) -> int:
    """Ham CSV'den değerlemeyi hesaplar ve data/processed/ altına yazar."""
    from fantasy9cat import pipeline
    from fantasy9cat.schema import DataValidationError

    raw_path = config.raw_csv_path(args.season)
    if not raw_path.exists():
        print(
            f"Hata: Ham veri bulunamadı: {raw_path}. Önce 'fetch' komutunu çalıştırın.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    try:
        meta = pipeline.run_compute(raw_path, config.PROCESSED_DIR, args.season)
    except DataValidationError as exc:
        print(f"Hata: Veri doğrulama başarısız. {exc}", file=sys.stderr)
        return EXIT_ERROR
    except ValueError as exc:
        print(f"Hata: Hesaplama yapılamadı. {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(
        f"{meta['n_players_total']} oyuncu değerlendi "
        f"(toplam: {meta['iterations_total']} iterasyon, "
        f"maç başı: {meta['iterations_per_game']} iterasyon): {config.PROCESSED_DIR}"
    )
    return EXIT_OK


def _cmd_report(args: argparse.Namespace) -> int:
    """İşlenmiş verilerden Hesaplama.md ve Deger.pdf'i üretir."""
    from fantasy9cat import report_md, report_pdf

    try:
        md_path = report_md.run_report_md(config.PROCESSED_DIR, config.OUTPUT_DIR)
        pdf_path, counts = report_pdf.run_report_pdf(config.PROCESSED_DIR, config.OUTPUT_DIR)
    except FileNotFoundError as exc:
        print(f"Hata: {exc}. Önce 'compute' komutunu çalıştırın.", file=sys.stderr)
        return EXIT_ERROR
    print(f"Yazıldı: {md_path}")
    print(
        f"Yazıldı: {pdf_path} (toplam: {counts[config.MODE_TOTAL]} satır, "
        f"maç başı: {counts[config.MODE_PER_GAME]} satır)"
    )
    return EXIT_OK


def _cmd_site(args: argparse.Namespace) -> int:
    """F13 ön koşulları tamamsa statik siteyi output/site/ altına üretir."""
    from fantasy9cat import site

    try:
        index = site.run_site(config.PROCESSED_DIR, config.OUTPUT_DIR)
    except site.SitePrerequisiteError as exc:
        print("Hata: Site üretilmedi; şu dosyalar eksik:", file=sys.stderr)
        for path in exc.missing:
            print(f"  - {path}", file=sys.stderr)
        print("Önce 'compute' ve 'report' komutlarını çalıştırın.", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(
            f"Hata: Site yazılamadı ({exc}). output/site/ içindeki bir dosya başka bir "
            "programda açık olabilir; kapatıp yeniden deneyin.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    print(f"Site yazıldı: {index}")
    return EXIT_OK


def _cmd_all(args: argparse.Namespace) -> int:
    """Ham CSV yoksa fetch, ardından compute → report → site; geçen süreyi loglar."""
    start = time.perf_counter()
    steps = [_cmd_compute, _cmd_report, _cmd_site]
    if not config.raw_csv_path(args.season).exists():
        logger.info("Ham veri yok; önce fetch çalıştırılıyor.")
        steps.insert(0, _cmd_fetch)
    else:
        logger.info("Ham veri mevcut; ağa çıkılmayacak.")
    for step in steps:
        code = step(args)
        if code != EXIT_OK:
            return code
    logger.info("Toplam süre: %.1f sn", time.perf_counter() - start)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Alt komutlarıyla argparse ayrıştırıcısını oluşturur."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--season", default=config.SEASON, help=f"Sezon (varsayılan: {config.SEASON})"
    )

    parser = argparse.ArgumentParser(
        prog="fantasy9cat", description="Fantezi NBA 9-cat oyuncu değerleme aracı"
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="KOMUT")
    commands = {
        "fetch": ("stats.nba.com'dan ham veriyi çeker -> data/raw/", _cmd_fetch),
        "compute": ("Değerlemeyi hesaplar -> data/processed/", _cmd_compute),
        "report": ("Hesaplama.md ve Deger.pdf üretir -> output/", _cmd_report),
        "site": ("Statik web sitesini üretir -> output/site/", _cmd_site),
        "all": ("compute -> report -> site (ham veri yoksa önce fetch)", _cmd_all),
    }
    for name, (help_text, handler) in commands.items():
        cmd = sub.add_parser(name, parents=[common], help=help_text, description=help_text)
        cmd.set_defaults(handler=handler)
    return parser


def _make_streams_safe() -> None:
    """Konsol kodlamasının basamadığı karakterleri (ör. Windows cp1254'te 'ć') '?' yapar."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    """CLI giriş noktası; çıkış kodunu döndürür."""
    _make_streams_safe()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
