// @category AtelierData
// Read private Python PE-IAT candidates and check whether Ghidra has
// recognized real instruction boundaries. Does not execute the original PE.
// No decoding, patching, license modification, or public address export.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.GsonBuilder;
import java.io.FileReader;
import java.io.FileWriter;
import java.util.*;

public class AtelierData_IAT_Instruction_Check extends GhidraScript {
    private static final int MAX_CANDIDATES = 200000;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 3)
            throw new IllegalArgumentException(
                "Expected: private-iat.json private-ghidra.json expected-sha256");
        JsonObject input;
        try (FileReader reader = new FileReader(args[0])) {
            input = JsonParser.parseReader(reader).getAsJsonObject();
        }
        String expected = args[2].toLowerCase(Locale.ROOT);
        if (!expected.matches("[0-9a-f]{64}") ||
            !expected.equals(input.get("sha256").getAsString().toLowerCase(Locale.ROOT)))
            throw new IllegalArgumentException("Input SHA256 mismatch");
        if (!"atelierdata-pe-iat-private-v1".equals(input.get("schema").getAsString()))
            throw new IllegalArgumentException("Unknown private report schema");
        JsonArray rows = input.getAsJsonArray("candidates");
        if (rows == null || rows.size() > MAX_CANDIDATES)
            throw new IllegalArgumentException("Excessive/missing candidate list");
        Map<String,Object> output = new LinkedHashMap<>();
        List<Map<String,Object>> checks = new ArrayList<>();
        int recognized = 0;
        int withReferences = 0;
        for (JsonElement element : rows) {
            monitor.checkCancelled();
            JsonObject item = element.getAsJsonObject();
            long va = item.get("instruction_va").getAsLong();
            Address address = toAddr(va);
            boolean inMemory = currentProgram.getMemory().contains(address);
            Instruction instruction = inMemory ?
                currentProgram.getListing().getInstructionAt(address) : null;
            boolean valid = false;
            int referenceCount = 0;
            String mnemonic = null;
            String function = null;
            if (instruction != null) {
                mnemonic = instruction.getMnemonicString();
                String expectedMnemonic = "call".equals(item.get("kind").getAsString())
                    ? "CALL" : "JMP";
                byte[] bytes = new byte[6];
                if (instruction.getLength() == 6 &&
                    currentProgram.getMemory().getBytes(address, bytes) == 6 &&
                    (bytes[0] & 255) == 255 &&
                    (bytes[1] & 255) == ("CALL".equals(expectedMnemonic) ? 0x15 : 0x25) &&
                    expectedMnemonic.equalsIgnoreCase(mnemonic)) {
                    valid = true;
                    recognized++;
                }
                referenceCount = instruction.getReferencesFrom().length;
                if (referenceCount > 0) withReferences++;
                Function f = getFunctionContaining(address);
                if (f != null) function = f.getName();
            }
            Map<String,Object> check = new LinkedHashMap<>();
            check.put("address", address.toString());
            check.put("symbol", item.get("symbol").getAsString());
            check.put("in_memory", inMemory);
            check.put("recognized_instruction", valid);
            check.put("mnemonic", mnemonic);
            check.put("references_from_instruction", referenceCount);
            check.put("containing_function", function);
            checks.add(check);
        }
        output.put("schema", "atelierdata-ghidra-iat-instruction-check-v1");
        output.put("source_sha256", expected);
        output.put("program_name", currentProgram.getName());
        output.put("candidate_count", rows.size());
        output.put("recognized_instruction_count", recognized);
        output.put("instructions_with_references", withReferences);
        output.put("target_executed", false);
        output.put("idf_decoder_proven", false);
        output.put("private_only", true);
        output.put("candidates", checks);
        output.put("limitations",
            "Recognized instruction boundaries and Ghidra references are not proof of a file loader. " +
            "A no-analysis import may yield zero recognized instructions.");
        try (FileWriter writer = new FileWriter(args[1])) {
            writer.write(new GsonBuilder().setPrettyPrinting().create().toJson(output));
        }
        println("ATELIERDATA_GHIDRA_IAT_CHECK=" + recognized + "/" + rows.size());
    }
}
