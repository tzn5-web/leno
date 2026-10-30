// @category AtelierData
// Static raw pointer candidate scan; never executes the imported PE.
// Raw LE32 matches are NOT proven code references or a decoder.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import com.google.gson.GsonBuilder;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class AtelierData_IDF_PointerCandidates extends GhidraScript {
    private static final String[] TERMS = {"inflate 1.2.3", "TFRMAUTODATABASE", ".IDF"};
    private static final int CHUNK = 1024 * 1024;
    private static final int MAX_TARGETS = 8;
    private static final int MAX_CANDIDATES = 32;
    private static final long MAX_SCAN = 128L * 1024 * 1024;

    private int locate(byte[] data, byte[] term, int start) {
        for (int i = start; i <= data.length - term.length; i++) {
            boolean matches = true;
            for (int j = 0; j < term.length; j++) {
                if (data[i + j] != term[j]) { matches = false; break; }
            }
            if (matches) return i;
        }
        return -1;
    }

    private interface MatchHandler {
        void hit(MemoryBlock block, Address address);
    }

    private void search(byte[] needle, MatchHandler callback) throws Exception {
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized()) continue;
            long size = Math.min(block.getSize(), MAX_SCAN);
            long offset = 0;
            byte[] carry = new byte[0];
            while (offset < size) {
                monitor.checkCancelled();
                int length = (int)Math.min(CHUNK, size - offset);
                byte[] chunk = new byte[length];
                int read = currentProgram.getMemory().getBytes(block.getStart().add(offset), chunk);
                if (read <= 0) break;
                byte[] data = new byte[carry.length + read];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(chunk, 0, data, carry.length, read);
                long base = offset - carry.length;
                int from = 0;
                while (true) {
                    int found = locate(data, needle, from);
                    if (found < 0) break;
                    long position = base + found;
                    if (position >= 0 && position + needle.length <= size) {
                        callback.hit(block, block.getStart().add(position));
                    }
                    from = found + 1;
                }
                int keep = Math.min(Math.max(needle.length - 1, 0), data.length);
                carry = Arrays.copyOfRange(data, data.length - keep, data.length);
                offset += read;
            }
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1 || args[0].isEmpty())
            throw new IllegalArgumentException("Private report path required");
        Map<String,Object> report = new LinkedHashMap<>();
        report.put("tool", "Ghidra byte-level static pointer candidate scanner");
        report.put("program_name", currentProgram.getName());
        report.put("language", currentProgram.getLanguageID().toString());
        report.put("target_executed", false);
        report.put("idf_decoder_proven", false);
        Map<String,Object> entries = new LinkedHashMap<>();
        for (String term : TERMS) {
            Map<String,Object> variants = new LinkedHashMap<>();
            for (String encoding : new String[]{"ascii", "utf16le"}) {
                byte[] pattern = term.getBytes(encoding.equals("ascii") ?
                        StandardCharsets.US_ASCII : StandardCharsets.UTF_16LE);
                List<Address> targets = new ArrayList<>();
                Set<String> unique = new HashSet<>();
                search(pattern, (block, addr) -> {
                    if (targets.size() < MAX_TARGETS && unique.add(addr.toString())) targets.add(addr);
                });
                List<Map<String,Object>> targetReports = new ArrayList<>();
                for (Address target : targets) {
                    long value = target.getOffset();
                    byte[] le = new byte[]{(byte)value, (byte)(value>>>8),
                                           (byte)(value>>>16), (byte)(value>>>24)};
                    List<Map<String,Object>> candidates = new ArrayList<>();
                    Set<String> seen = new HashSet<>();
                    search(le, (block, addr) -> {
                        if (candidates.size() >= MAX_CANDIDATES || !seen.add(addr.toString())) return;
                        Map<String,Object> item = new LinkedHashMap<>();
                        item.put("address", addr.toString());
                        item.put("block", block.getName());
                        item.put("executable_block", block.isExecute());
                        candidates.add(item);
                    });
                    Map<String,Object> item = new LinkedHashMap<>();
                    item.put("target_address", target.toString());
                    item.put("raw_le32_candidates", candidates);
                    item.put("truncated_at", MAX_CANDIDATES);
                    targetReports.add(item);
                }
                variants.put(encoding, targetReports);
            }
            entries.put(term, variants);
        }
        report.put("terms", entries);
        report.put("limitations", "Raw little-endian 32-bit matches can be incidental; not verified code xrefs. Missing matches do not exclude dynamic address construction.");
        try (FileWriter out = new FileWriter(args[0])) {
            out.write(new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        println("ATELIERDATA_GHIDRA_POINTER_CANDIDATES=" + args[0]);
    }
}
