// @category AtelierData
// Read-only, SHA256-bound IDF string/reference triage for authorized interoperability.
// This script does NOT execute the target, decode IDF, or inspect licensing.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import com.google.gson.GsonBuilder;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

public class AtelierData_IDF_Xrefs_Verified extends GhidraScript {
    private static final String[] TERMS = {
        "MODELS.IDF", "CONST.IDF", "CSS.IDF", "DTC.IDF", ".IDF",
        "inflate 1.2.3", "TFRMAUTODATABASE", "ChilkatCrypt2"
    };
    private static final int CHUNK = 1024 * 1024;
    private static final int MAX_HITS_PER_PATTERN = 32;
    private static final int MAX_REFS_PER_HIT = 32;
    private static final long MAX_SCAN_TOTAL = 128L * 1024L * 1024L;
    private static final long MAX_PE = 64L * 1024L * 1024L;

    private static String hex(byte[] digest) {
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b & 255));
        return sb.toString();
    }

    private static String[] fileHashes(File source) throws Exception {
        if (!source.isFile() || source.length() < 256 || source.length() > MAX_PE)
            throw new IllegalArgumentException("Missing or oversized original PE");
        MessageDigest sha256 = MessageDigest.getInstance("SHA-256");
        MessageDigest md5 = MessageDigest.getInstance("MD5");
        try (InputStream in = new BufferedInputStream(new FileInputStream(source))) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) != -1) {
                sha256.update(buf, 0, n);
                md5.update(buf, 0, n);
            }
        }
        return new String[]{hex(sha256.digest()), hex(md5.digest())};
    }

    private static int indexOf(byte[] data, byte[] pattern, int start) {
        outer: for (int i = start; i <= data.length - pattern.length; i++) {
            for (int j = 0; j < pattern.length; j++)
                if (data[i + j] != pattern[j]) continue outer;
            return i;
        }
        return -1;
    }

    private static Map<String,Object> row(Address address, int limit,
                                           AtelierData_IDF_Xrefs_Verified script) {
        Map<String,Object> item = new LinkedHashMap<>();
        item.put("address", address.toString());
        List<String> xrefs = new ArrayList<>();
        int codeRefs = 0;
        int totalRefs = 0;
        for (Reference ref : script.currentProgram.getReferenceManager().getReferencesTo(address)) {
            totalRefs++;
            if (script.currentProgram.getListing().getInstructionContaining(ref.getFromAddress()) != null)
                codeRefs++;
            if (xrefs.size() < limit) xrefs.add(ref.getFromAddress().toString());
        }
        item.put("reference_count", totalRefs);
        item.put("code_reference_count", codeRefs);
        item.put("references_from_truncated", totalRefs > limit);
        item.put("references_from", xrefs);
        return item;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 4)
            throw new IllegalArgumentException(
                "Usage: original-pe expected-sha256 private-report.json public-aggregate.json");
        File source = new File(args[0]).getCanonicalFile();
        File privateOutput = new File(args[2]).getCanonicalFile();
        File publicOutput = new File(args[3]).getCanonicalFile();
        if (source.equals(privateOutput) || source.equals(publicOutput) ||
            privateOutput.equals(publicOutput))
            throw new IllegalArgumentException("Outputs must differ from original PE and each other");
        String expected = args[1].toLowerCase(Locale.ROOT);
        if (!expected.matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("Expected SHA256 must be 64 hex digits");
        String[] hashes = fileHashes(source);
        if (!expected.equals(hashes[0]))
            throw new IllegalArgumentException("Original PE SHA256 mismatch");
        String importedMd5 = currentProgram.getExecutableMD5();
        if (importedMd5 == null || !hashes[1].equalsIgnoreCase(importedMd5))
            throw new IllegalArgumentException("Ghidra program MD5 differs from verified original PE");

        Map<String,Object> privateReport = new LinkedHashMap<>();
        Map<String,Object> publicReport = new LinkedHashMap<>();
        Map<String,List<Map<String,Object>>> privateHits = new LinkedHashMap<>();
        Map<String,Map<String,Object>> aggregates = new LinkedHashMap<>();
        int maxPattern = 0;
        for (String term : TERMS) maxPattern = Math.max(maxPattern, term.length() * 2);
        long remaining = MAX_SCAN_TOTAL;
        long scanned = 0;
        int initializedBlocks = 0;
        boolean scanTruncated = false;
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            monitor.checkCancelled();
            if (!block.isInitialized()) continue;
            initializedBlocks++;
            if (remaining <= 0) { scanTruncated = true; break; }
            long limit = Math.min(block.getSize(), remaining);
            if (limit < block.getSize()) scanTruncated = true;
            long offset = 0;
            byte[] carry = new byte[0];
            while (offset < limit) {
                monitor.checkCancelled();
                int take = (int)Math.min(CHUNK, limit - offset);
                byte[] chunk = new byte[take];
                int read = currentProgram.getMemory().getBytes(block.getStart().add(offset), chunk);
                if (read <= 0) throw new IOException("Unmapped initialized block bytes");
                byte[] data = new byte[carry.length + read];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(chunk, 0, data, carry.length, read);
                long base = offset - carry.length;
                for (String term : TERMS) {
                    for (String encoding : new String[]{"ascii", "utf16le"}) {
                        String key = term + ":" + encoding;
                        List<Map<String,Object>> rows = privateHits.computeIfAbsent(
                            key, k -> new ArrayList<>());
                        byte[] pattern = term.getBytes(encoding.equals("ascii") ?
                            StandardCharsets.US_ASCII : StandardCharsets.UTF_16LE);
                        int pos = 0;
                        while (rows.size() < MAX_HITS_PER_PATTERN) {
                            int at = indexOf(data, pattern, pos);
                            if (at < 0) break;
                            long location = base + at;
                            if (location >= 0 && location + pattern.length <= limit) {
                                Address address = block.getStart().add(location);
                                // Cross-chunk matches are deduplicated by exact Ghidra address.
                                boolean seen = false;
                                for (Map<String,Object> previous : rows) {
                                    if (address.toString().equals(previous.get("address"))) {
                                        seen = true; break;
                                    }
                                }
                                if (!seen) rows.add(row(address, MAX_REFS_PER_HIT, this));
                            }
                            pos = at + 1;
                        }
                    }
                }
                int keep = Math.min(maxPattern - 1, data.length);
                carry = Arrays.copyOfRange(data, data.length - keep, data.length);
                offset += read;
                scanned += read;
            }
            remaining -= offset;
        }
        for (String term : TERMS) {
            for (String encoding : new String[]{"ascii", "utf16le"}) {
                String key = term + ":" + encoding;
                List<Map<String,Object>> rows = privateHits.getOrDefault(key, Collections.emptyList());
                int refs = 0, codeRefs = 0;
                for (Map<String,Object> item : rows) {
                    refs += (Integer)item.get("reference_count");
                    codeRefs += (Integer)item.get("code_reference_count");
                }
                Map<String,Object> summary = new LinkedHashMap<>();
                summary.put("hits_at_most_32", rows.size());
                summary.put("hit_cap_reached", rows.size() == MAX_HITS_PER_PATTERN);
                summary.put("ghidra_existing_references", refs);
                summary.put("ghidra_existing_code_references", codeRefs);
                aggregates.put(key, summary);
            }
        }
        publicReport.put("schema", "atelierdata-ghidra-idf-xrefs-public-v1");
        publicReport.put("original_sha256_verified", expected);
        publicReport.put("ghidra_program_md5_verified", true);
        publicReport.put("initialized_blocks", initializedBlocks);
        publicReport.put("scanned_bytes", scanned);
        publicReport.put("scan_truncated", scanTruncated);
        publicReport.put("patterns", aggregates);
        publicReport.put("target_executed", false);
        publicReport.put("idf_decoder_proven", false);
        publicReport.put("limitations",
            "Existing Ghidra references depend on analysis coverage; zero references without disassembly is inconclusive. Literal matches do not prove IDF loading.");
        privateReport.putAll(publicReport);
        privateReport.put("schema", "atelierdata-ghidra-idf-xrefs-private-v1");
        privateReport.put("private_only", true);
        privateReport.put("hits_with_addresses", privateHits);
        File parent = privateOutput.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs())
            throw new IOException("Cannot create private output directory");
        parent = publicOutput.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs())
            throw new IOException("Cannot create public output directory");
        try (Writer writer = new BufferedWriter(new FileWriter(privateOutput))) {
            new GsonBuilder().setPrettyPrinting().create().toJson(privateReport, writer);
        }
        try (Writer writer = new BufferedWriter(new FileWriter(publicOutput))) {
            new GsonBuilder().setPrettyPrinting().create().toJson(publicReport, writer);
        }
        println("ATELIERDATA_GHIDRA_IDF_XREFS_VERIFIED=REPORT_WRITTEN scanned=" + scanned);
    }
}
