"""Canonical source coverage for every visible subject. File version: 1.0.0.

This verifies source lineage, not facial recognition or visual identity fidelity.
It never changes an approved packet, image, creative decision or spending grant.
"""
FILE_VERSION = '1.0.0'
import re

ID = re.compile(r'CHAR-[0-9]{3}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def bind_sources(sources, characters, primary_id):
    if not isinstance(characters, list) or not 1 <= len(characters) <= 4:
        raise ValueError('Supply every visible canonical character packet, up to four.')
    identities = [s.get('source_sha256') for s in sources if s.get('role') == 'identity']
    if not identities or len(identities) != len(set(identities)):
        raise ValueError('Each visible identity needs one distinct pinned source.')
    packets = {}
    for packet in characters:
        cid = packet.get('character_id', '')
        if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in packets or packet.get('identity_locked') is not True:
            raise ValueError('Visible characters must have unique locked canonical IDs.')
        hashes = packet.get('source_asset_hashes')
        if not isinstance(hashes, dict) or not hashes or any(
                not isinstance(v, str) or not SHA.fullmatch(v) for v in hashes.values()):
            raise ValueError('Canonical character source hashes are required.')
        packets[cid] = packet
    if primary_id not in packets or len(identities) != len(packets):
        raise ValueError('Reference sources must cover exactly the declared visible cast.')
    bindings = []
    used = set()
    for sha in identities:
        matches = [(cid, asset) for cid, packet in packets.items()
                   for asset, value in packet['source_asset_hashes'].items() if value == sha]
        if len(matches) != 1 or matches[0][0] in used:
            raise ValueError('Each identity source must identify exactly one visible canonical character.')
        cid, asset = matches[0]
        used.add(cid)
        bindings.append({'status':'canonical_source_hash_matched', 'character_id':cid,
                         'identity_source_sha256':sha, 'identity_asset_id':asset,
                         'biometric_identity_verified':False})
    if used != set(packets):
        raise ValueError('Missing visible canonical character source.')
    return bindings


def validate_descriptor(descriptor):
    """Legacy single-subject descriptors remain valid; multi-source ones need coverage."""
    sources = descriptor.get('source_request', {}).get('sources', [])
    identities = [s.get('source_sha256') for s in sources if s.get('role') == 'identity']
    bindings = descriptor.get('canonical_cast_bindings')
    primary = descriptor.get('canonical_identity_binding', {})
    if bindings is None:
        if len(identities) != 1 or identities != [primary.get('identity_source_sha256')]:
            raise ValueError('Multiple visible identities require explicit canonical cast bindings.')
        return [primary]
    if not isinstance(bindings, list) or len(bindings) != len(identities) or not 1 <= len(bindings) <= 4:
        raise ValueError('Visible cast binding count differs from reference sources.')
    ids = [b.get('character_id') for b in bindings]
    if len(ids) != len(set(ids)) or any(not isinstance(cid, str) or not ID.fullmatch(cid) for cid in ids):
        raise ValueError('Visible cast IDs must be distinct and canonical.')
    if [b.get('identity_source_sha256') for b in bindings] != identities or len(identities) != len(set(identities)):
        raise ValueError('Visible cast source order or hashes changed.')
    for binding in bindings:
        if (binding.get('status') != 'canonical_source_hash_matched'
                or binding.get('biometric_identity_verified') is not False
                or not isinstance(binding.get('identity_asset_id'), str)
                or not binding['identity_asset_id']
                or not isinstance(binding.get('identity_source_sha256'), str)
                or not SHA.fullmatch(binding['identity_source_sha256'])):
            raise ValueError('Invalid visible canonical source binding.')
    selected = [b for b in bindings if b['character_id'] == descriptor['scope']['character_id']]
    if selected != [primary]:
        raise ValueError('Primary identity differs from the visible cast binding.')
    return bindings


def validate_for_job(descriptor, director, primary_character):
    """Compare frame source coverage to the exact hash-sealed Director visible cast."""
    refs = director.get('character_refs') or [primary_character]
    if not isinstance(refs, list):
        raise ValueError('Exact Director character references required.')
    expected = {ref.get('character_id'): ref for ref in refs}
    if len(expected) != len(refs) or primary_character.get('character_id') not in expected:
        raise ValueError('Director visible cast differs from primary canonical character.')
    # Older approved-job descriptors store image-plan references rather than request sources.
    if 'source_request' not in descriptor:
        actual = [descriptor.get('canonical_identity_binding', {})]
    else:
        actual = validate_descriptor(descriptor)
    if {b.get('character_id') for b in actual} != set(expected):
        raise ValueError('Frame does not provide canonical source evidence for every visible character.')
    for binding in actual:
        ref = expected[binding['character_id']]
        if (ref.get('identity_locked') is not True or ref.get('source_asset_hashes', {}).get(
                binding['identity_asset_id']) != binding['identity_source_sha256']):
            raise ValueError('Frame visible identity differs from the approved Director source.')
    return {'schema':'joat.visible_cast_source_check.v1', 'file_version':FILE_VERSION,
            'character_ids':sorted(expected), 'all_visible_sources_matched':True,
            'biometric_identity_verified':False, 'production_qc_approved':False, 'gpu_called':False}
