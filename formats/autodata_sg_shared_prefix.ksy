meta:
  id: autodata_sg_shared_prefix
  title: Empirical shared prefix in Autodata SGINT and SGOPS IDF
  file-extension: idf
  ks-version: 0.10
doc: |
  PRELIMINARY opaque byte layout, not a decoded Autodata IDF format.
  Verified ONLY for the first 412818 bytes of COMMON/SGINT.IDF and
  COMMON/SGOPS.IDF (19658 consecutive records * 21 bytes).
  In corresponding rows, the first 8 bytes are identical across both
  files; the last 13 bytes usually differ. Their meanings are UNKNOWN.
  All remaining file contents are out of scope and are not parsed.
seq:
  - id: opaque_records
    type: opaque_record
    repeat: expr
    repeat-expr: 19658
types:
  opaque_record:
    seq:
      - id: shared_token
        size: 8
        doc: Identical byte token at matching record offset; meaning unknown
      - id: variable_payload
        size: 13
        doc: Opaque variable bytes; meaning and encoding unknown
