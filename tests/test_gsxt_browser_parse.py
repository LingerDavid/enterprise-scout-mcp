"""GSXT browser HTML parsing."""

from __future__ import annotations

from enterprise_scout_mcp.channels.official.parse import classify_browser_block, parse_search_html


def test_parse_search_html_embedded_json():
    html = """
    <script>
    var data = {"entName": "苏州挚途科技有限公司", "uniscId": "91320507MA1YW0G9XC"};
    </script>
    """
    row = parse_search_html(html, keyword="苏州挚途")
    assert row is not None
    assert row["credit_code"] == "91320507MA1YW0G9XC"
    assert "苏州挚途" in row["name"]


def test_parse_search_html_skips_ct_page():
    html = '<html><script src="/ctct_bundle_fdab54c7.js"></script></html>'
    assert parse_search_html(html) is None


def test_parse_search_list_item_with_geetest_scripts():
    """Result pages always embed geetest JS — must still parse USCC cards."""
    html = """
    <html><script src="https://gcaptcha4.geetest.com/load"></script>
    <script src="/ctct_bundle_fdab54c7.js"></script>
    <title>国家企业信用信息公示系统</title>
    <input id="keyword" name="searchword"/>
    <a class="search_list_item db" href="/x">
      <h1 class="f20"><font color="red">苏州挚途</font>科技有限公司</h1>
      <div class="div-map2">统一社会信用代码：
        <span class="g3">91320507MA1YW0G9XC</span>
      </div>
    </a>
    </html>
    """
    row = parse_search_html(html, keyword="苏州挚途")
    assert row is not None
    assert row["credit_code"] == "91320507MA1YW0G9XC"
    assert "苏州挚途科技有限公司" == row["name"]


def test_classify_browser_block_ctct_on_normal_page_not_blocked():
    html = (
        '<html><script src="/ctct_bundle_fdab54c7.js"></script>'
        '<input id="keyword" name="keyword"/>国家企业信用信息公示系统</html>'
    )
    assert classify_browser_block(html) is None


def test_classify_browser_block_geetest_on_normal_page_not_blocked():
    html = '<html><script>geetest</script><input name="keyword"/>国家企业信用信息公示系统</html>'
    assert classify_browser_block(html) is None
