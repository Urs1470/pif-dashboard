"""Parser pentru export ABB Drive Composer Pro (`.dcparamsbak`).

.dcparamsbak este de fapt un fisier ZIP care contine:
  - parameters.dcparams (XML cu toti parametrii)
  - OfflineDriveInfo.xml (metadate drive: Family, Software, Variant)
  - 00010000_*.bin (firmware metadata, ignorat)

Schema XML parameters.dcparams:
  <ParameterFileContent>
    <DriveProperties>...</DriveProperties>
    <ParameterList>
      <DriveParameter>
        <Group>1</Group>
        <Index>1</Index>
        <Name>Motor speed used</Name>
        <Value xsi:type="xsd:double">0</Value>
        <DefaultValue xsi:type="xsd:int">0</DefaultValue>
        <Unit>rpm</Unit>
        <IsSignal>true</IsSignal>           <- read-only signal/monitor
        <IsAtDefault>false</IsAtDefault>
        <ValueNames>
          <ValueListItem><Name>Off</Name><Value>0</Value></ValueListItem>
          ...
        </ValueNames>
      </DriveParameter>
      ...
    </ParameterList>
  </ParameterFileContent>

Format DB ABB (validat in scripts/audit_pdf.py parse_abb): "Group.Index" cu Index
zero-padded la 2 cifre (ex: "1.01", "30.11", "99.04").

Filtre implicite:
- Skip IsSignal=true (read-only signals, nu config)
- Skip Value == DefaultValue (parametri neschimbati - ABB nu seteaza IsAtDefault corect)
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List


def _is_zip(raw_bytes: bytes) -> bool:
    return len(raw_bytes) >= 4 and raw_bytes[:4] == b'PK\x03\x04'


def _value_names_map(elem):
    """Construieste dict {valoare_str: nume_text} din <ValueNames><ValueListItem>...</>."""
    out = {}
    vn = elem.find('ValueNames')
    if vn is None:
        return out
    for item in vn:
        if item.tag.split('}')[-1] != 'ValueListItem':
            continue
        n = item.findtext('Name') or item.findtext('{*}Name')
        v = item.findtext('Value') or item.findtext('{*}Value')
        if n is not None and v is not None:
            out[str(v).strip()] = (n or '').strip()
    return out


def _format_value(raw_val: str, unit: str, names_map):
    """Compune valoarea afisabila: numeric + nume enum + unit (cand unit != NoUnit)."""
    raw_val = (raw_val or '').strip()
    text = raw_val
    name = names_map.get(raw_val)
    if name:
        text = f"{name} [{raw_val}]"
    if unit and unit != 'NoUnit':
        text = f"{text} {unit}".strip()
    return text


def parse(content, filename: str = '', skip_at_default: bool = True) -> List[Dict]:
    """Parseaza un .dcparamsbak ABB si returneaza lista params modificati.

    Args:
        content: bytes ai fisierului sau path. Daca primeste path, deschide ca file.
        filename: nume original (informativ)
        skip_at_default: daca True, sare peste parametrii cu value == default
    """
    # Accept bytes sau path
    if isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        with open(content, 'rb') as f:
            raw = f.read()

    if not _is_zip(raw):
        # Fallback: poate e XML direct (parameters.dcparams brut)
        xml_data = raw
    else:
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return []
        # Cauta parameters.dcparams in zip
        target = None
        for name in zf.namelist():
            if name.lower().endswith('.dcparams'):
                target = name
                break
        if target is None:
            return []
        xml_data = zf.read(target)
        zf.close()

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    plist = root.find('ParameterList')
    if plist is None:
        # Compatibilitate cu namespace
        plist = root.find('{*}ParameterList')
    if plist is None:
        return []

    result = []
    for elem in plist:
        if elem.tag.split('}')[-1] != 'DriveParameter':
            continue

        is_signal = (elem.findtext('IsSignal') or '').lower() == 'true'
        if is_signal:
            continue

        group = (elem.findtext('Group') or '').strip()
        idx = (elem.findtext('Index') or '').strip()
        if not group or not idx:
            continue

        raw_value = (elem.findtext('Value') or '').strip()
        raw_default = (elem.findtext('DefaultValue') or '').strip()

        if skip_at_default and raw_value == raw_default:
            continue

        name = (elem.findtext('Name') or '').strip()
        unit = (elem.findtext('Unit') or '').strip()
        names_map = _value_names_map(elem)

        # ABB DB convention: Group.Index cu zero-pad pe 2 cifre la Index
        try:
            db_id = f"{int(group)}.{int(idx):02d}"
        except ValueError:
            db_id = f"{group}.{idx}"

        value_display = _format_value(raw_value, unit, names_map)
        default_display = _format_value(raw_default, unit, names_map)

        result.append({
            'db_id': db_id,
            'raw_id': f"{group}.{idx}",
            'p_code': '',
            'name': name,
            'value': value_display,
            'default': default_display,
            'setups': [],
            'conflict': False,
            'per_setup': {},
        })

    # Sortare numerica (Group, Index)
    def sort_key(p):
        parts = p['db_id'].split('.')
        try:
            return (int(parts[0]), int(parts[1]))
        except Exception:
            return (9999, 9999)

    result.sort(key=sort_key)
    return result


def read_drive_info(content) -> dict:
    """Citeste metadatele drive din OfflineDriveInfo.xml + DriveProperties.

    Returneaza dict cu chei din ambele surse:
      - OfflineDriveInfo.xml: Family, Software, Variant
      - parameters.dcparams > DriveProperties: Name, DriveModel,
        SystemSoftwareVersion, ControlBoardType, ChannelAddress, Address
    """
    if isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        with open(content, 'rb') as f:
            raw = f.read()
    if not _is_zip(raw):
        return {}
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return {}
    info = {}

    # 1. OfflineDriveInfo.xml (existent)
    for name in zf.namelist():
        if name.lower().endswith('offlinedriveinfo.xml'):
            try:
                tree = ET.fromstring(zf.read(name))
                for child in tree:
                    tag = child.tag.split('}')[-1]
                    if child.text:
                        info[tag] = child.text.strip()
            except ET.ParseError:
                pass
            break

    # 2. DriveProperties din parameters.dcparams
    _DRIVE_PROPS = {'Name', 'DriveModel', 'SystemSoftwareVersion',
                    'ControlBoardType', 'ChannelAddress', 'Address',
                    'Kind', 'ProductFamily', 'ManualIdentifier'}
    for name in zf.namelist():
        if name.lower().endswith('.dcparams'):
            try:
                root = ET.fromstring(zf.read(name))
                dp = root.find('DriveProperties')
                if dp is None:
                    dp = root.find('{*}DriveProperties')
                if dp is not None:
                    for child in dp:
                        tag = child.tag.split('}')[-1]
                        if tag in _DRIVE_PROPS and child.text:
                            info[tag] = child.text.strip()
            except ET.ParseError:
                pass
            break

    zf.close()
    return info


def parse_full(content, filename: str = '') -> List[Dict]:
    """Parseaza un .dcparamsbak si returneaza TOTI parametrii cu metadate extinse.

    Spre deosebire de parse(), include:
    - Toti parametrii (inclusiv cei la default si signals)
    - Metadate extinse: unit, min, max, data_type, value_names, is_signal

    Folosit pentru enrichment-ul bazei de date parametri_master.
    """
    if isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        with open(content, 'rb') as f:
            raw = f.read()

    if not _is_zip(raw):
        xml_data = raw
    else:
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return []
        target = None
        for name in zf.namelist():
            if name.lower().endswith('.dcparams'):
                target = name
                break
        if target is None:
            return []
        xml_data = zf.read(target)
        zf.close()

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    plist = root.find('ParameterList')
    if plist is None:
        plist = root.find('{*}ParameterList')
    if plist is None:
        return []

    result = []
    for elem in plist:
        if elem.tag.split('}')[-1] != 'DriveParameter':
            continue

        group = (elem.findtext('Group') or '').strip()
        idx = (elem.findtext('Index') or '').strip()
        if not group or not idx:
            continue

        try:
            db_id = f"{int(group)}.{int(idx):02d}"
        except ValueError:
            db_id = f"{group}.{idx}"

        name = (elem.findtext('Name') or '').strip()
        unit = (elem.findtext('Unit') or '').strip()
        if unit == 'NoUnit':
            unit = ''

        raw_default = (elem.findtext('DefaultValue') or '').strip()
        raw_value = (elem.findtext('Value') or '').strip()
        is_signal = (elem.findtext('IsSignal') or '').lower() == 'true'

        # Min/Max
        raw_min = (elem.findtext('Min') or '').strip()
        raw_max = (elem.findtext('Max') or '').strip()

        # Data type
        data_type = (elem.findtext('NativeDataType') or '').strip()
        param_type = (elem.findtext('Type') or '').strip()

        # Enum labels
        names_map = _value_names_map(elem)

        result.append({
            'db_id': db_id,
            'raw_id': f"{group}.{idx}",
            'name': name,
            'unit': unit,
            'default_value': raw_default,
            'value': raw_value,
            'min': raw_min,
            'max': raw_max,
            'data_type': data_type,
            'param_type': param_type,
            'value_names': names_map if names_map else None,
            'is_signal': is_signal,
        })

    # Sortare numerica (Group, Index)
    def sort_key(p):
        parts = p['db_id'].split('.')
        try:
            return (int(parts[0]), int(parts[1]))
        except Exception:
            return (9999, 9999)

    result.sort(key=sort_key)
    return result


if __name__ == '__main__':
    import sys
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Downloads\PresaFinal.dcparamsbak'
    with open(path, 'rb') as f:
        raw = f.read()
    info = read_drive_info(raw)
    print(f"Drive info: {info}")
    parsed = parse(raw, filename=path)
    print(f"Total params modificati: {len(parsed)}")
    parsed_all = parse(raw, filename=path, skip_at_default=False)
    print(f"Total params (toate, fara signals): {len(parsed_all)}")
    print()
    print(json.dumps(parsed[:15], indent=2, ensure_ascii=False))
