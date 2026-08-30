// Whole-program, build-keyed fact exporter for headless Ghidra analysis.
//
// The output contains normalized function identities, body ranges and hashes,
// plus direct internal call edges. It deliberately emits no executable bytes,
// disassembly, decompiler text, local variables, or reconstructed source.
// @category IntoTheBreach

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressRangeIterator;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;

public class ExportItbProgramFacts extends GhidraScript {
    private static final String FORMAT_VERSION = "1";

    private static String cleanField(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\\", "\\\\")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
            .replace("\n", "\\n");
    }

    private static String hex(byte[] value) {
        StringBuilder result = new StringBuilder(value.length * 2);
        for (byte item : value) {
            result.append(String.format("%02x", item & 0xff));
        }
        return result.toString();
    }

    private static String canonicalRva(long value) {
        if (value < 0) {
            throw new IllegalArgumentException("negative RVA");
        }
        return String.format("0x%08x", value);
    }

    private String rva(Address address) {
        Address imageBase = currentProgram.getImageBase();
        if (address == null || !address.getAddressSpace().equals(imageBase.getAddressSpace())) {
            return "";
        }
        try {
            return canonicalRva(address.subtract(imageBase));
        }
        catch (RuntimeException exception) {
            return "";
        }
    }

    private String bodySha256(AddressSetView body) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        Memory memory = currentProgram.getMemory();
        AddressRangeIterator ranges = body.getAddressRanges(true);
        byte[] buffer = new byte[64 * 1024];
        while (ranges.hasNext()) {
            AddressRange range = ranges.next();
            Address cursor = range.getMinAddress();
            long remaining = range.getLength();
            while (remaining > 0) {
                int wanted = (int) Math.min(buffer.length, remaining);
                int read = memory.getBytes(cursor, buffer, 0, wanted);
                if (read != wanted) {
                    throw new IllegalStateException(
                        "short memory read at " + cursor + ": " + read + "/" + wanted
                    );
                }
                digest.update(buffer, 0, read);
                cursor = cursor.add(read);
                remaining -= read;
            }
        }
        return hex(digest.digest());
    }

    private void writeRow(PrintWriter output, String... fields) {
        for (int index = 0; index < fields.length; index++) {
            if (index != 0) {
                output.print('\t');
            }
            output.print(cleanField(fields[index]));
        }
        output.println();
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportItbProgramFacts.java OUTPUT"
            );
        }

        File outputFile = new File(args[0]).getCanonicalFile();
        File parent = outputFile.getParentFile();
        if (parent == null || !parent.isDirectory()) {
            throw new IllegalArgumentException("output parent must already exist");
        }

        FunctionManager functionManager = currentProgram.getFunctionManager();
        Listing listing = currentProgram.getListing();
        Memory memory = currentProgram.getMemory();
        List<Function> functions = new ArrayList<>();
        FunctionIterator iterator = functionManager.getFunctions(true);
        while (iterator.hasNext()) {
            Function function = iterator.next();
            if (
                function.isExternal()
                || function.getBody().isEmpty()
                || !memory.contains(function.getEntryPoint())
                || rva(function.getEntryPoint()).isEmpty()
            ) {
                continue;
            }
            functions.add(function);
        }
        Collections.sort(
            functions,
            Comparator.comparing(Function::getEntryPoint)
        );

        List<String[]> rangeRows = new ArrayList<>();
        List<String[]> callRows = new ArrayList<>();
        int omittedCallTargets = 0;
        for (Function function : functions) {
            String entry = rva(function.getEntryPoint());
            AddressRangeIterator ranges = function.getBody().getAddressRanges(true);
            while (ranges.hasNext()) {
                AddressRange range = ranges.next();
                String start = rva(range.getMinAddress());
                if (start.isEmpty()) {
                    throw new IllegalStateException(
                        "function body range is outside the image: " + function.getName(true)
                    );
                }
                rangeRows.add(
                    new String[] {
                        entry,
                        start,
                        Long.toString(range.getLength()),
                    }
                );
            }

            InstructionIterator instructions = listing.getInstructions(function.getBody(), true);
            while (instructions.hasNext()) {
                Instruction instruction = instructions.next();
                if (!instruction.getFlowType().isCall()) {
                    continue;
                }
                Address[] targets = instruction.getFlows();
                if (instruction.getFlowType().isComputed() || targets.length == 0) {
                    omittedCallTargets += 1;
                    continue;
                }
                for (Address target : targets) {
                    String targetRva = rva(target);
                    if (targetRva.isEmpty() || !memory.contains(target)) {
                        omittedCallTargets += 1;
                        continue;
                    }
                    Function targetFunction = functionManager.getFunctionContaining(target);
                    callRows.add(
                        new String[] {
                            entry,
                            rva(instruction.getAddress()),
                            targetRva,
                            targetFunction == null ? "" : rva(targetFunction.getEntryPoint()),
                            targetFunction == null ? "" : targetFunction.getName(true),
                        }
                    );
                }
            }
        }

        Collections.sort(
            callRows,
            Comparator.comparing((String[] row) -> row[0])
                .thenComparing(row -> row[1])
                .thenComparing(row -> row[2])
                .thenComparing(row -> row[3])
                .thenComparing(row -> row[4])
        );

        try (
            PrintWriter output = new PrintWriter(
                new BufferedWriter(
                    new FileWriter(outputFile, StandardCharsets.UTF_8, false)
                )
            )
        ) {
            writeRow(output, "meta", "format_version", FORMAT_VERSION);
            writeRow(output, "meta", "ghidra_version", Application.getApplicationVersion());
            writeRow(output, "meta", "program_name", currentProgram.getName());
            writeRow(output, "meta", "language_id", currentProgram.getLanguageID().toString());
            writeRow(
                output,
                "meta",
                "compiler_spec_id",
                currentProgram.getCompilerSpec().getCompilerSpecID().toString()
            );
            writeRow(
                output,
                "meta",
                "image_base",
                canonicalRva(currentProgram.getImageBase().getOffset())
            );
            writeRow(output, "meta", "function_count", Integer.toString(functions.size()));
            writeRow(output, "meta", "range_count", Integer.toString(rangeRows.size()));
            writeRow(
                output,
                "meta",
                "direct_internal_call_count",
                Integer.toString(callRows.size())
            );
            writeRow(
                output,
                "meta",
                "omitted_call_target_count",
                Integer.toString(omittedCallTargets)
            );

            for (Function function : functions) {
                writeRow(
                    output,
                    "function",
                    rva(function.getEntryPoint()),
                    function.getName(),
                    function.getParentNamespace().getName(true),
                    function.getSymbol().getSource().toString(),
                    function.isThunk() ? "1" : "0",
                    Long.toString(function.getBody().getNumAddresses()),
                    bodySha256(function.getBody())
                );
            }
            for (String[] row : rangeRows) {
                writeRow(output, "range", row[0], row[1], row[2]);
            }
            for (String[] row : callRows) {
                writeRow(
                    output,
                    "call",
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4]
                );
            }
        }

        println(
            "Wrote " + functions.size() + " functions, " + rangeRows.size()
            + " ranges, and " + callRows.size() + " direct internal calls to "
            + outputFile
        );
    }
}
