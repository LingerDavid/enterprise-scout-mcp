"""L1 official registry channels."""

__all__ = ["GsxtOfficialChannel"]


def __getattr__(name: str):
    if name == "GsxtOfficialChannel":
        from enterprise_scout_mcp.channels.official.gsxt import GsxtOfficialChannel

        return GsxtOfficialChannel
    raise AttributeError(name)
