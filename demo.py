import logging

from demo_support.render import render_demo_output
from demo_support.scenario import run_demo


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    configure_logging()
    demo_result = run_demo()
    render_demo_output(demo_result)


if __name__ == "__main__":
    main()
