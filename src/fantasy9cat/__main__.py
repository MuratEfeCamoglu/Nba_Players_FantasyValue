"""Komut satırı arayüzü: fetch, compute, report, site, all."""

import argparse
import io
import logging
import sys

from fantasy9cat import config

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_IMPLEMENTED = 2


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


def _cmd_not_implemented(args: argparse.Namespace) -> int:
    """Henüz yazılmamış alt komutlar için 2 döner."""
    print(f"'{args.command}' komutu henüz uygulanmadı.", file=sys.stderr)
    return EXIT_NOT_IMPLEMENTED


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
        "compute": ("Değerlemeyi hesaplar -> data/processed/", _cmd_not_implemented),
        "report": ("Hesaplama.md ve Deger.pdf üretir -> output/", _cmd_not_implemented),
        "site": ("Statik web sitesini üretir -> output/site/", _cmd_not_implemented),
        "all": ("compute -> report -> site (ham veri yoksa önce fetch)", _cmd_not_implemented),
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
