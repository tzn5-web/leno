// @category AtelierData
// Static keyword and cross-reference inspection only. Does not execute the imported PE.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import com.google.gson.GsonBuilder;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class AtelierData_IDF_Xrefs extends GhidraScript {
    private static final String[] TERMS = {"MODELS.IDF", "CONST.IDF", "CSS.IDF", "DTC.IDF", ".IDF",
            "inflate 1.2.3", "TFRMAUTODATABASE", "ChilkatCrypt2"};
    private static final long MAX_SCAN = 128L * 1024 * 1024;
    private static final int CHUNK = 1024 * 1024;
    private static final int OVERLAP = 128;
    private static final int MAX_HITS = 32;

    private int indexOf(byte[] haystack, byte[] needle, int from) {
        for (int i = from; i <= haystack.length - needle.length; i++) {
            boolean match = true;
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) { match = false; break; }
            }
            if (match) return i;
        }
        return -1;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1 || args[0].isEmpty()) {
            throw new IllegalArgumentException("Provide private JSON report path");
        }
        Map<String,Object> report = new LinkedHashMap<>();
        report.put("tool", "Ghidra static Java script AtelierData_IDF_Xrefs");
        report.put("program_name", currentProgram.getName());
        report.put("language_id", currentProgram.getLanguageID().toString());
        report.put("target_executed", false);
        report.put("idf_decoder_proven", false);
        List<Map<String,Object>> blocks = new ArrayList<>();
        Map<String,Object> hits = new LinkedHashMap<>();
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized()) continue;
            long size = Math.min(block.getSize(), MAX_SCAN);
            Map<String,Object> blockInfo = new LinkedHashMap<>();
            blockInfo.put("name", block.getName());
            blockInfo.put("bytes", block.getSize());
            blockInfo.put("scanned_bytes", size);
            blocks.add(blockInfo);
            Map<String,List<Map<String,Object>>> found = new LinkedHashMap<>();
            Map<String,Set<Long>> seen = new HashMap<>();
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
                for (String term : TERMS) {
                    for (String encoding : new String[]{"ascii", "utf16le"}) {
                        byte[] pattern = term.getBytes(encoding.equals("ascii") ?
                                StandardCharsets.US_ASCII : StandardCharsets.UTF_16LE);
                        String key = term + ":" + encoding;
                        List<Map<String,Object>> entries = found.computeIfAbsent(key, k -> new ArrayList<>());
                        Set<Long> used = seen.computeIfAbsent(key, k -> new HashSet<>());
                        int at = 0;
                        while (entries.size() < MAX_HITS) {
                            int i = indexOf(data, pattern, at);
                            if (i < 0) break;
                            long position = base + i;
                            if (position >= 0 && position < size && used.add(position)) {
                                Address addr = block.getStart().add(position);
                                List<String> references = new ArrayList<>();
                                for (Reference ref : currentProgram.getReferenceManager().getReferencesTo(addr)) {
                                    if (references.size() >= 16) break;
                                    references.add(ref.getFromAddress().toString());
                                }
                                Map<String,Object> item = new LinkedHashMap<>();
                                item.put("address", addr.toString());
                                item.put("references_from", references);
                                entries.add(item);
                            }
                            at = i + 1;
                        }
                    }
                }
                int keep = Math.min(OVERLAP, data.length);
                carry = Arrays.copyOfRange(data, data.length - keep, data.length);
                offset += read;
            }
            found.values().removeIf(List::isEmpty);
            if (!found.isEmpty()) hits.put(block.getName(), found);
        }
        report.put("blocks", blocks);
        report.put("keyword_hits", hits);
        report.put("limitations", "Literal keyword matches and existing xrefs only; not proof of an IDF loader or decryption.");
        try (FileWriter out = new FileWriter(args[0])) {
            out.write(new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        println("ATELIERDATA_GHIDRA_STATIC_REPORT=" + args[0]);
    }
}
