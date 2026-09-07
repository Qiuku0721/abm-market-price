from app.wifi import _parse_mdns


def test_parse_mdns():
    text = """List of discovered mdns services
Pixel_8          inet    192.168.1.50  37123  tls
Xiaomi 14        inet    192.168.1.60  41899
"""
    r = _parse_mdns(text)
    assert len(r) == 2
    assert r[0]["name"] == "Pixel_8"
    assert r[0]["host"] == "192.168.1.50"
    assert r[0]["port"] == 37123
    assert r[0]["tls"] is True
    assert r[1]["tls"] is False
    assert r[1]["host"] == "192.168.1.60"
