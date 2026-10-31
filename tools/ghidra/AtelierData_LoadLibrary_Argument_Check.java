// @category AtelierData
// Ghidra static-only check of a SHA256-gated private Python triage report.
// Does not run, patch, decode or redistribute the original executable.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import com.google.gson.*;
import java.io.*;
import java.util.*;

public class AtelierData_LoadLibrary_Argument_Check extends GhidraScript {
    private static final int MAX_CANDIDATES = 20000;
    private static final int MAX_STRING = 160;

    private int read32(byte[] bytes, int start) {
        return (bytes[start] & 255) | ((bytes[start + 1] & 255) << 8) |
               ((bytes[start + 2] & 255) << 16) | ((bytes[start + 3] & 255) << 24);
    }

    private String readAscii(Address address) throws Exception {
        StringBuilder value = new StringBuilder();
        for (int i = 0; i < MAX_STRING; i++) {
            Address at = address.add(i);
            if (!currentProgram.getMemory().contains(at)) return null;
            int b = currentProgram.getMemory().getByte(at) & 255;
            if (b == 0) return value.length() == 0 ? null : value.toString();
            if (b < 32 || b > 126) return null;
            value.append((char)b);
        }
        return null;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2)
            throw new IllegalArgumentException("Expected private-input.json private-ghidra-output.json");
        JsonObject input;
        try (Reader reader = new FileReader(args[0])) {
            input = JsonParser.parseReader(reader).getAsJsonObject();
        }
        if (!"atelierdata-loadlibrary-literal-private-v1".equals(input.get("schema").getAsString()))
            throw new IllegalArgumentException("Unknown input schema");
        String expectedMd5 = input.get("md5").getAsString().toLowerCase(Locale.ROOT);
        String programMd5 = currentProgram.getExecutableMD5();
        if (!expectedMd5.matches("[a-f0-9]{32}") || programMd5 == null ||
            !expectedMd5.equals(programMd5.toLowerCase(Locale.ROOT)))
            throw new IllegalArgumentException("Imported Ghidra program MD5 mismatch");
        JsonArray candidates = input.getAsJsonArray("candidates");
        if (candidates == null || candidates.size() > MAX_CANDIDATES)
            throw new IllegalArgumentException("Invalid candidate count");
        // Conservative, bounded direct-call graph from Ghidra-declared entry points.
        // Indirect/dynamic calls are not resolved; absence from this graph is not
        // proof of unreachable code. These are static edges, not runtime traces.
        Set<Function> entryGraph = new HashSet<>();
        ArrayDeque<Function> pending = new ArrayDeque<>();
        ghidra.program.model.address.AddressIterator entryAddresses =
            currentProgram.getSymbolTable().getExternalEntryPointIterator();
        int entryRoots = 0;
        while (entryAddresses.hasNext()) {
            monitor.checkCancelled();
            Function root = currentProgram.getFunctionManager()
                .getFunctionContaining(entryAddresses.next());
            if (root != null && entryGraph.add(root)) {
                pending.add(root);
                entryRoots++;
            }
        }
        final int MAX_GRAPH_FUNCTIONS = 20000;
        while (!pending.isEmpty() && entryGraph.size() < MAX_GRAPH_FUNCTIONS) {
            monitor.checkCancelled();
            Function function = pending.removeFirst();
            for (Function called : function.getCalledFunctions(monitor)) {
                if (called != null && !called.isExternal() && entryGraph.add(called))
                    pending.addLast(called);
            }
        }
        boolean graphComplete = pending.isEmpty();
        int graphMatchedCandidates = 0;
        int recognized = 0, literalVerified = 0, iatReferenced = 0;
        List<Map<String,Object>> rows = new ArrayList<>();
        for (JsonElement element : candidates) {
            monitor.checkCancelled();
            JsonObject candidate = element.getAsJsonObject();
            long callVa = candidate.get("call_va").getAsLong();
            long pushVa = candidate.get("push_va").getAsLong();
            long ptrVa = candidate.get("pointer_va").getAsLong();
            long iatVa = candidate.get("iat_va").getAsLong();
            Address call = toAddr(callVa), push = toAddr(pushVa), pointer = toAddr(ptrVa);
            Address iat = toAddr(iatVa);
            Instruction pushInst = currentProgram.getListing().getInstructionAt(push);
            Instruction callInst = currentProgram.getListing().getInstructionAt(call);
            boolean exact = false, refToIat = false, literalMatches = false;
            if (pushInst != null && callInst != null && callVa == pushVa + 5 &&
                pushInst.getLength() == 5 && callInst.getLength() == 6 &&
                "PUSH".equalsIgnoreCase(pushInst.getMnemonicString()) &&
                "CALL".equalsIgnoreCase(callInst.getMnemonicString())) {
                byte[] p = new byte[5], c = new byte[6];
                if (currentProgram.getMemory().getBytes(push,p) == 5 &&
                    currentProgram.getMemory().getBytes(call,c) == 6 &&
                    (p[0] & 255) == 0x68 && (c[0] & 255) == 0xff &&
                    (c[1] & 255) == 0x15 &&
                    Integer.toUnsignedLong(read32(p,1)) == ptrVa &&
                    Integer.toUnsignedLong(read32(c,2)) == iatVa) {
                    exact = true;
                    recognized++;
                    for (Reference ref : callInst.getReferencesFrom()) {
                        if (ref.getToAddress().equals(iat)) { refToIat = true; break; }
                    }
                    if (refToIat) iatReferenced++;
                }
            }
            if (exact && !candidate.get("literal").isJsonNull()) {
                String original = candidate.get("literal").getAsString();
                literalMatches = original.equals(readAscii(pointer));
                if (literalMatches) literalVerified++;
            }
            Function owner = getFunctionContaining(call);
            Map<String,Object> row = new LinkedHashMap<>();
            row.put("call_va",callVa);
            row.put("push_call_instruction_verified",exact);
            row.put("literal_pointer_verified",literalMatches);
            row.put("ghidra_reference_to_iat",refToIat);
            row.put("containing_function",owner == null ? null : owner.getName());
            boolean inEntryGraph = exact && owner != null && entryGraph.contains(owner);
            row.put("in_ghidra_entrypoint_direct_call_graph",inEntryGraph);
            if (inEntryGraph) graphMatchedCandidates++;
            rows.add(row);
        }
        Map<String,Object> report = new LinkedHashMap<>();
        report.put("schema","atelierdata-ghidra-loadlibrary-private-v1");
        report.put("source_sha256",input.get("sha256").getAsString());
        report.put("ghidra_executable_md5_verified",true);
        report.put("candidate_count",candidates.size());
        report.put("recognized_instruction_pairs",recognized);
        report.put("verified_literal_pointers",literalVerified);
        report.put("iat_references",iatReferenced);
        report.put("target_executed",false);
        report.put("cfg_reachability_proven",false);
        report.put("ghidra_declared_entry_roots_with_functions",entryRoots);
        report.put("direct_call_graph_functions_visited",entryGraph.size());
        report.put("direct_call_graph_complete_within_budget",graphComplete);
        report.put("verified_candidates_in_direct_call_graph",graphMatchedCandidates);
        report.put("direct_call_graph_limitations",
            "Static direct edges only; no indirect calls, loader callbacks or runtime reachability proof.");
        report.put("idf_decoder_proven",false);
        report.put("candidates",rows);
        report.put("limitations","Static instruction boundaries and bounded Ghidra direct-call graph only; not proof of runtime reachability.");
        try (Writer writer = new FileWriter(args[1])) {
            new GsonBuilder().setPrettyPrinting().create().toJson(report,writer);
        }
        println("ATELIERDATA_GHIDRA_LOADLIBRARY=" + recognized + "/" + candidates.size());
    }
}
