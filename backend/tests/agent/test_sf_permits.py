"""
Tests for fetch_sf_permits tool.
All external HTTP calls are mocked — no real network requests.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch


def _http_html_mock(html: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = html
    return resp


_ADDRESS_LIST_HTML = """
<table>
<tr><td><a href="default.aspx?page=AddressData2&amp;AddressID=111">Select</a></td><td>319 </td><td>PLYMOUTH AV</td><td>&nbsp;</td><td>7107</td><td>057</td></tr>
<tr><td><a href="default.aspx?page=AddressData2&amp;AddressID=222">Select</a></td><td>319 </td><td>PLYMOUTH ST</td><td>&nbsp;</td><td>7107</td><td>058</td></tr>
</table>
"""

_SELECTED_ADDRESS_HTML = """
<p>You selected:</p>
<span id="InfoReq1_lblAddress">319 PLYMOUTH AV</span>
"""

_EID_PANEL_HTML = """
<p><strong><span id="InfoReq1_lblPermitTypeResults">(Electrical or Solar permits matching the selected address.)</span></strong></p>
<table id="InfoReq1_dgEID">
<tr bgcolor="#EFEBEF"><th>Permit #</th><th>Block</th><th>Lot</th><th>Street #</th><th>Street Name</th><th>Unit</th><th>Current Stage</th><th>Stage Date</th></tr>
<tr bgcolor="White">
<td><a href="default.aspx?page=EID_PermitDetails&amp;PermitNo=E200304106449">E200304106449</a></td>
<td>7107</td><td>057</td><td>319</td><td>PLYMOUTH AV</td><td>&nbsp;</td><td>COMPLETE</td><td>5/12/2003</td>
</tr>
</table>
"""

_PID_PANEL_HTML = """
<p><strong><span id="InfoReq1_lblPermitTypeResults"><font color="Maroon">Sorry, no existing plumbing permits were found for this address.</font></span></strong></p>
"""

_BID_PANEL_HTML = """
<p><strong><span id="InfoReq1_lblPermitTypeResults"><font color="Maroon">Sorry, no existing building permits were found for this address.</font></span></strong></p>
"""

_CTS_PANEL_HTML = """
<p><strong><span id="InfoReq1_lblPermitTypeResults">(Complaints matching the selected address.)</span></strong></p>
<table id="InfoReq1_dgCTS">
<tr><th>Complaint #</th><th>Expired</th><th>Date Filed</th><th>Status</th><th>Div</th><th>Block</th><th>Lot</th><th>Street #</th><th>Street Name</th></tr>
<tr>
<td><a href="default.aspx?page=AddressComplaint&amp;ComplaintNo=202295394"><strike>202295394</strike></a></td>
<td>&nbsp;</td><td>09/09/2022</td><td>CLOSED</td><td>HIS</td><td>7107</td><td>057</td><td>319</td><td>PLYMOUTH AV</td>
</tr>
</table>
"""

_EID_DETAIL_HTML = """
<html>
  <body>
    <p>
      Permit Details Report
      Application Number: EW202109018103
      Address(es): 2175 / 006J : 2142 43RD AV
      Description: UPGRADE EXISTING 70 AMP MAIN SERVICE PANEL TO 125 AMP ONLY, NO ADDING LOAD.
      Stage: Action Date Stage Comments
    </p>
  </body>
</html>
"""


class TestFetchSfPermits:
    async def test_returns_dbi_permits_and_complaints(self):
        from agent.tools.sf_permits import fetch_sf_permits

        with patch("agent.tools.sf_permits.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _http_html_mock(_ADDRESS_LIST_HTML),
                _http_html_mock(_SELECTED_ADDRESS_HTML),
                _http_html_mock(_EID_PANEL_HTML),
                _http_html_mock(_PID_PANEL_HTML),
                _http_html_mock(_BID_PANEL_HTML),
                _http_html_mock(_CTS_PANEL_HTML),
                _http_html_mock(_EID_DETAIL_HTML),
            ]

            result = await fetch_sf_permits(
                address_matched="319 PLYMOUTH AVE, SAN FRANCISCO, CA, 94112",
                unit=None,
            )

        assert result["source"] == "dbi"
        assert result["source_detail"] is None
        assert result["open_permits_count"] == 0
        assert result["complaints_open_count"] == 0
        assert result["permit_counts_by_type"]["electrical"] == 1
        assert len(result["permits"]) == 1
        assert len(result["complaints"]) == 1
        assert result["permits"][0]["permit_number"] == "E200304106449"
        assert "UPGRADE EXISTING 70 AMP MAIN SERVICE PANEL TO 125 AMP ONLY, NO ADDING LOAD." in (
            result["permits"][0]["work_description"] or ""
        )
        assert result["permits"][0]["llm_summary"] is not None
        assert result["permits"][0]["llm_impact"] in ("positive", "negative")
        assert result["complaints"][0]["complaint_number"] == "202295394"

    async def test_uses_exact_suffix_match_when_multiple_address_ids_exist(self):
        from agent.tools.sf_permits import fetch_sf_permits

        with patch("agent.tools.sf_permits.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _http_html_mock(_ADDRESS_LIST_HTML),
                _http_html_mock(_SELECTED_ADDRESS_HTML),
                _http_html_mock(_EID_PANEL_HTML),
                _http_html_mock(_PID_PANEL_HTML),
                _http_html_mock(_BID_PANEL_HTML),
                _http_html_mock(_CTS_PANEL_HTML),
                _http_html_mock(_EID_DETAIL_HTML),
            ]

            await fetch_sf_permits(
                address_matched="319 PLYMOUTH AVE, SAN FRANCISCO, CA, 94112",
                unit=None,
            )

        # Second GET is selected address page URL; should choose AddressID=111 (PLYMOUTH AV)
        selected_url = mock_client.get.call_args_list[1].args[0]
        assert "AddressID=111" in selected_url

    async def test_returns_empty_shape_on_dbi_failure(self):
        from agent.tools.sf_permits import fetch_sf_permits

        with patch("agent.tools.sf_permits.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = RuntimeError("network down")

            result = await fetch_sf_permits(
                address_matched="450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
                unit=None,
            )

        assert result["source"] == "none"
        assert result["source_detail"] is not None
        assert result["permits"] == []
        assert result["complaints"] == []
        assert result["open_permits_count"] == 0
        assert result["complaints_open_count"] == 0

    async def test_enriches_permit_with_llm_summary_and_impact_when_enabled(self):
        from agent.tools.sf_permits import fetch_sf_permits

        llm_response = MagicMock()
        llm_response.content = [MagicMock(type="text", text='{"summary":"Main panel upgrade and new branch circuits.","impact":"positive"}')]

        with patch.dict(os.environ, {"ENABLE_PERMIT_LLM": "1", "ANTHROPIC_API_KEY": "test-key"}, clear=True), \
             patch("agent.tools.sf_permits.httpx.AsyncClient") as mock_http_cls, \
             patch("agent.tools.sf_permits.anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [
                _http_html_mock(_ADDRESS_LIST_HTML),
                _http_html_mock(_SELECTED_ADDRESS_HTML),
                _http_html_mock(_EID_PANEL_HTML),
                _http_html_mock(_PID_PANEL_HTML),
                _http_html_mock(_BID_PANEL_HTML),
                _http_html_mock(_CTS_PANEL_HTML),
                _http_html_mock(_EID_DETAIL_HTML),
            ]

            mock_anthropic_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic_client
            mock_anthropic_client.messages.create.return_value = llm_response

            result = await fetch_sf_permits(
                address_matched="319 PLYMOUTH AVE, SAN FRANCISCO, CA, 94112",
                unit=None,
            )

        permit = result["permits"][0]
        assert permit["llm_summary"] == "Main panel upgrade and new branch circuits."
        assert permit["llm_impact"] == "positive"
