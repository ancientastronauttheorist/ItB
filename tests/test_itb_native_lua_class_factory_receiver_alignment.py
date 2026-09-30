"""Aligned producer storage; actual native execution is subprocess-isolated."""

import copy
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_class_factory_receiver_alignment as m

ROOT = Path(__file__).resolve().parents[1]


def fixture(vector):
    rv = m.full._record_vector(vector)
    base = m.full.record._base_vector(rv)
    prototype = m.full.factory._fixture(base)
    return prototype, m.install(vector, prototype)


@pytest.mark.parametrize("vector", m.vectors())
def test_exact_disjoint_spans_original_pages_and_no_prebuilt_fields(vector):
    prototype, f = fixture(vector)
    assert f["userdata"] == 0x0FFFFFCC and f["record"] == 0x10000100
    assert f["userdata"] + 52 == 0x10000000 and f["userdata"] + 72 < f["record"]
    assert set(f["pages"]) - set(prototype["pages"]) >= {0x0FFFF000, 0x10000000}
    for page, payload in prototype["pages"].items():
        # The normal extension explicitly binds initializer/context/heap pages.
        normal = m.full._extend_fixture(vector, prototype)
        assert f["pages"][page] == normal["pages"][page]
    assert f["pages"][0x0FFFF000] == b"\xa5" * 4096
    assert f["pages"][0x10000000] == b"\xa5" * 4096
    before = copy.deepcopy(prototype)
    f["pages"][0x0FFFF000] = b"\0" * 4096
    assert prototype == before


@pytest.mark.parametrize(
    "change", ["extra", "profile_bool", "registry", "alias", "length"]
)
def test_unreviewed_vectors_rejected(change):
    v = m.vectors()[0]
    prototype, _ = fixture(v)
    changed = dict(v)
    if change == "extra":
        changed["unknown"] = 0
    elif change == "profile_bool":
        changed["profile"] = False
    elif change == "registry":
        changed["registry_profile"] = 3
    elif change == "alias":
        changed["equal_pointers"] = True
    else:
        changed["length"] = 1
    with pytest.raises(
        RuntimeError, match="unreviewed factory receiver alignment vector"
    ):
        m.install(changed, prototype)


@pytest.mark.parametrize("page", [0x0FFFF000, 0x10000000])
def test_existing_page_collision_rejected(page):
    v = m.vectors()[0]
    prototype, _ = fixture(v)
    prototype["pages"][page] = b"\x12" * 4096
    with pytest.raises(
        RuntimeError, match="factory receiver alignment overlaps original pages"
    ):
        m.install(v, prototype)


def test_vectors_are_detached_exact_domain():
    assert len(m.vectors()) == 18
    assert {v["profile"] for v in m.vectors()} == {0, 1}
    assert {v["registry_profile"] for v in m.vectors()} == {0, 1, 2}
    assert {v["length"] for v in m.vectors()} == {0, 16, 255}
    v = m.vectors()
    v[0]["length"] = 999
    assert m.vectors()[0]["length"] == 0


NATIVE = r"""
import json,os
from pathlib import Path
from src.observatory import native_lua_class_factory_receiver_alignment as m
f=m.full;common=f.factory
root=Path('data/observatory/programs');prefix='windows_build_13725832_31fe35265598_'
sources={k:json.loads((root/(prefix+('program_facts' if k=='program_facts' else kind.removeprefix('pe_'))+'.json')).read_text()) for k,(kind,sha) in f.SOURCE_PINS.items()}
f._preflight(sources)
data,image,digest=f._load_executable(Path(os.environ['ITB_EXACT_EXE']))
assert digest==f.EXE_SHA256
payload,points,continuation=f._load_code(data,image,sources)
captured={}
def capture(machine,negative,fixture,expected,lua,ids):
    captured.update(pages={p:bytes(machine.mem_read(p,4096)) for p in fixture['pages']},closure=lua.stack[-1])
for vector in m.vectors():
    rv=f._record_vector(vector);base=f.record._base_vector(rv)
    installed=dict(continuation,extend_fixture=lambda v,p:m.install(vector,p),lua_observer=lambda v,p:f._Lua(base,p),endpoint_mutation=capture)
    observation=common._run_case(payload,points,base,continuation=installed)
    pages=captured['pages'];raw=lambda a,w=4:common._raw(pages,a,w)
    assert observation['registers']['eax']==1
    assert captured['closure']==('closure',0x6ec110,('userdata',0x0fffffcc))
    assert raw(0x10000000)==0x10000100 and raw(0x10000004)==0
    assert [raw(0x10000100+o) for o in (0,4,8)]==[0x10000100]*3
    assert raw(0x1000010c,2)==0x0101
    assert bytes(pages[0x10000000][0x10e:0x118])==b'\xa5'*10
    assert [raw(0x0fffffcc+o) for o in (4,8,12)]==[0,0,0]
    assert [raw(0x0fffffcc+o) for o in (24,32,40)]==[installed['extend_fixture'](base,common._fixture(base))['spec']['references'][i] for i in (2,0,1)]
    before=common._fixture(base)
    # Original unused userdata page and original record allocation pages survive.
    assert pages[0x14000000]==before['pages'][0x14000000]
    assert pages[0x16000000]==b'\xc7'*4096 and pages[0x16001000]==b'\xc7'*4096
for kind in ('userdata','record_marker','first_reference','factory_return'):
    try:common._run_case(payload,points,base,kind,continuation=installed)
    except f.ConformanceError as error:assert str(error)=='factory protected memory differs',(kind,error)
    else:raise AssertionError('alignment control survived: '+kind)
print('18 aligned native factory returns; 4 exact protected controls')
"""


def test_actual_native_aligned_factory_returns_and_protected_controls():
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    result = subprocess.run(
        [sys.executable, "-c", NATIVE], cwd=ROOT, capture_output=True, timeout=180
    )
    assert result.returncode == 0, result.stderr
    assert (
        result.stderr == b""
        and result.stdout.strip()
        == b"18 aligned native factory returns; 4 exact protected controls"
    )
