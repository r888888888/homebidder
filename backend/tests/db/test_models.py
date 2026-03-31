from db.models import Listing


def test_listing_has_address_input_column():
    assert "address_input" in Listing.__table__.c


def test_listing_has_address_matched_column():
    assert "address_matched" in Listing.__table__.c


def test_listing_address_matched_is_unique():
    col = Listing.__table__.c["address_matched"]
    assert col.unique is True


def test_listing_has_coordinate_columns():
    cols = Listing.__table__.c
    assert "latitude" in cols
    assert "longitude" in cols


def test_listing_has_geo_columns():
    cols = Listing.__table__.c
    assert "county" in cols
    assert "state" in cols
    assert "zip_code" in cols


def test_listing_has_prop13_columns():
    cols = Listing.__table__.c
    assert "prop13_assessed_value" in cols
    assert "prop13_base_year" in cols
    assert "prop13_annual_tax" in cols


def test_listing_has_no_url_column():
    assert "url" not in Listing.__table__.c
