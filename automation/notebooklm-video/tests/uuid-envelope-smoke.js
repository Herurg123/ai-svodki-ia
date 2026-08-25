"use strict";

const crypto = require("crypto");

function encode(base64Value) {
  const protectedBytes = Buffer.from(base64Value, "base64");
  const lengthMask = crypto.randomBytes(4);
  const maskedLength = Buffer.alloc(4);
  maskedLength.writeUInt32BE(
    (protectedBytes.length ^ lengthMask.readUInt32BE(0)) >>> 0,
    0
  );
  const header = Buffer.concat([lengthMask, maskedLength]);
  const rawLength = header.length + protectedBytes.length;
  const paddedLength = Math.ceil(rawLength / 16) * 16;
  const payload = Buffer.alloc(paddedLength);
  header.copy(payload, 0);
  protectedBytes.copy(payload, header.length);
  if (paddedLength > rawLength) {
    crypto.randomFillSync(payload, rawLength, paddedLength - rawLength);
  }
  const blocks = [];
  for (let offset = 0; offset < payload.length; offset += 16) {
    const hex = payload.subarray(offset, offset + 16).toString("hex");
    blocks.push(
      `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`
    );
  }
  return blocks.join(".");
}

function decode(value) {
  const blocks = value.split(".");
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  if (blocks.some((block) => !uuidPattern.test(block))) {
    throw new Error("bad UUID envelope");
  }
  const payload = Buffer.concat(
    blocks.map((block) => Buffer.from(block.replace(/-/g, ""), "hex"))
  );
  const protectedLength =
    (payload.readUInt32BE(0) ^ payload.readUInt32BE(4)) >>> 0;
  return payload.subarray(8, 8 + protectedLength).toString("base64");
}

for (const length of [1, 16, 17, 64, 208, 333]) {
  const source = crypto.randomBytes(length).toString("base64");
  const encoded = encode(source);
  const decoded = decode(encoded);
  if (decoded !== source) {
    throw new Error(`roundtrip failed for ${length}`);
  }
}

console.log("UUID-like protected envelope smoke test: OK");
