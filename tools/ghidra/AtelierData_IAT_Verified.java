// @category AtelierData
// Verified static IAT candidate triage. Never executes or modifies original code.
// Requires private PE triage JSON + exact local original PE file, both SHA256 checked.
// Output with offsets stays private; optional public output contains aggregate counts.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.GsonBuilder;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

public class AtelierData_IAT_Verified extends GhidraScript {
    private static final int MAX_CANDIDATES = 200000;
    private static final long MAX_BINARY_BYTES = 64L * 1024L * 1024L;

    private static String hex(byte[] digest) {
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) sb.append(String.format("%02x", b & 255));
        return sb.toString();
    }

    private static String[] hashes(File file) throws Exception {
        if (!file.isFile() || file.length() > MAX_BINARY_BYTES)
            throw new IllegalArgumentException("Original PE missing or exceeds size bound");
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        MessageDigest md5 = MessageDigest.getInstance("MD5");
        try (InputStream in = new BufferedInputStream(new FileInputStream(file))) {
            byte[] buffer = new byte[65536];
            int n;
            while ((n = in.read(buffer)) != -1) {
                sha.update(buffer, 0, n);
                md5.update(buffer, 0, n);
            }
        }
        return new String[] {hex(sha.digest()), hex(md5.digest())};
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 4 && args.length != 5)
            throw new IllegalArgumentException(
                "Expected: private-iat.json private-ghidra.json expected-sha256 original-pe [public-summary.json]");
        // Canonicalize every path before opening an output stream. A typo must
        // never truncate the original executable or the private input evidence.
        File privateInput = new File(args[0]).getCanonicalFile();
        File privateOutput = new File(args[1]).getCanonicalFile();
        File originalInput = new File(args[3]).getCanonicalFile();
        File publicOutput = args.length == 5 ? new File(args[4]).getCanonicalFile() : null;
        if (privateOutput.equals(privateInput) || privateOutput.equals(originalInput) ||
            (publicOutput != null && (publicOutput.equals(originalInput) ||
             publicOutput.equals(privateInput) || publicOutput.equals(privateOutput))))
            throw new IllegalArgumentException("Output path must differ from all input paths");
        String expected = args[2].toLowerCase(Locale.ROOT);
        if (!expected.matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("Expected SHA256 must be 64 hexadecimal characters");
        String[] actual = hashes(originalInput);
        if (!expected.equals(actual[0]))
            throw new IllegalArgumentException("Original PE SHA256 mismatch");
        // Ghidra's imported-file MD5 binds currentProgram to the independently
        // SHA256-checked local file. No reliance on a user-provided report alone.
        String importedMd5 = currentProgram.getExecutableMD5();
        if (importedMd5 == null || importedMd5.length() != 32 ||
            !actual[1].equalsIgnoreCase(importedMd5))
            throw new IllegalArgumentException("Ghidra program does not match original PE MD5");

        JsonObject input;
        try (Reader reader = new BufferedReader(new FileReader(privateInput))) {
            input = JsonParser.parseReader(reader).getAsJsonObject();
        }
        if (!"atelierdata-pe-iat-private-v1".equals(input.get("schema").getAsString()) ||
            !expected.equals(input.get("sha256").getAsString().toLowerCase(Locale.ROOT)))
            throw new IllegalArgumentException("Private report schema or SHA256 mismatch");
        JsonArray rows = input.getAsJsonArray("candidates");
        if (rows == null || rows.size() > MAX_CANDIDATES)
            throw new IllegalArgumentException("Excessive or missing candidate list");
        int recognized = 0, references = 0, mapped = 0;
        List<Map<String,Object>> checks = new ArrayList<>();
        for (JsonElement element : rows) {
            monitor.checkCancelled();
            JsonObject row = element.getAsJsonObject();
            if (!row.has("iat_va"))
                throw new IllegalArgumentException("Regenerate private triage report with iat_va");
            long va = row.get("instruction_va").getAsLong();
            long iatVa = row.get("iat_va").getAsLong();
            if (va < 0 || va > 0xffffffffL || iatVa < 0 || iatVa > 0xffffffffL)
                throw new IllegalArgumentException("Non-PE32 address");
            String kind = row.get("kind").getAsString();
            if (!"call".equals(kind) && !"jump".equals(kind))
                throw new IllegalArgumentException("Unknown candidate kind");
            Address addr = toAddr(va);
            boolean inMemory = currentProgram.getMemory().contains(addr);
            if (inMemory) mapped++;
            Instruction instruction = inMemory ? currentProgram.getListing().getInstructionAt(addr) : null;
            boolean valid = false, referenceToIat = false;
            String mnemonic = null;
            if (instruction != null) {
                mnemonic = instruction.getMnemonicString();
                byte[] bytes = new byte[6];
                int read = instruction.getLength() == 6 ?
                    currentProgram.getMemory().getBytes(addr, bytes) : -1;
                if (read == 6) {
                    long operand = (bytes[2] & 255L) | ((bytes[3] & 255L) << 8) |
                                   ((bytes[4] & 255L) << 16) | ((bytes[5] & 255L) << 24);
                    valid = (bytes[0] & 255) == 0xff &&
                            (bytes[1] & 255) == ("call".equals(kind) ? 0x15 : 0x25) &&
                            ("call".equals(kind) ? "CALL" : "JMP").equalsIgnoreCase(mnemonic) &&
                            operand == iatVa;
                }
                if (valid) {
                    recognized++;
                    for (Reference ref : instruction.getReferencesFrom()) {
                        if (ref.getToAddress().getOffset() == iatVa) {
                            referenceToIat = true;
                            references++;
                            break;
                        }
                    }
                }
            }
            Map<String,Object> item = new LinkedHashMap<>();
            item.put("instruction_va", va);
            item.put("iat_va", iatVa);
            item.put("symbol", row.get("symbol").getAsString());
            item.put("kind", kind);
            item.put("in_memory", inMemory);
            item.put("instruction_opcode_operand_verified", valid);
            item.put("ghidra_reference_to_iat", referenceToIat);
            item.put("mnemonic", mnemonic);
            checks.add(item);
        }
        Map<String,Object> publicReport = new LinkedHashMap<>();
        publicReport.put("schema", "atelierdata-ghidra-iat-public-v2");
        publicReport.put("original_sha256_verified", expected);
        publicReport.put("ghidra_program_md5_verified", true);
        publicReport.put("candidate_count", rows.size());
        publicReport.put("candidates_mapped_to_memory", mapped);
        publicReport.put("opcode_operand_verified", recognized);
        publicReport.put("ghidra_references_to_iat", references);
        publicReport.put("target_executed", false);
        publicReport.put("idf_decoder_proven", false);
        publicReport.put("limitations",
            "Instruction and operand matches do not prove runtime execution, IDF decoding or a license.");
        Map<String,Object> privateReport = new LinkedHashMap<>(publicReport);
        privateReport.put("schema", "atelierdata-ghidra-iat-private-v2");
        privateReport.put("private_only", true);
        privateReport.put("candidates", checks);
        try (Writer writer = new BufferedWriter(new FileWriter(privateOutput))) {
            new GsonBuilder().setPrettyPrinting().create().toJson(privateReport, writer);
        }
        if (args.length == 5) {
            try (Writer writer = new BufferedWriter(new FileWriter(publicOutput))) {
                new GsonBuilder().setPrettyPrinting().create().toJson(publicReport, writer);
            }
        }
        println("ATELIERDATA_GHIDRA_VERIFIED=" + recognized + "/" + rows.size() +
                " referenced=" + references);
    }
}
