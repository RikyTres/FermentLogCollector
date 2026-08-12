from importlib import metadata


DISTRIBUTION_NAME = __package__.replace("_", "-")


def app_version() -> str:
    try:
        return metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return "0+development"
