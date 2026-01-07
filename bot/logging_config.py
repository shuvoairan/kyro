import logging

def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt)

    logging.getLogger("discord").setLevel(logging.DEBUG if debug else logging.INFO)
