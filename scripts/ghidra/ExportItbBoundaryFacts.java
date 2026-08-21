// Build-keyed boundary evidence exporter for headless Ghidra analysis.
// @category IntoTheBreach

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressRangeIterator;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class ExportItbBoundaryFacts extends GhidraScript {
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

    private static String functionEntry(Function function) {
        return function == null ? "" : function.getEntryPoint().toString();
    }

    private static String functionName(Function function) {
        return function == null ? "" : function.getName(true);
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
        if (args.length < 2) {
            throw new IllegalArgumentException(
                "usage: ExportItbBoundaryFacts.java OUTPUT LABEL=ADDRESS [LABEL=ADDRESS ...] " +
                "(Windows batch launchers may pass LABEL ADDRESS pairs)"
            );
        }

        File outputFile = new File(args[0]).getCanonicalFile();
        File parent = outputFile.getParentFile();
        if (parent == null || !parent.isDirectory()) {
            throw new IllegalArgumentException("output parent must already exist");
        }

        FunctionManager functions = currentProgram.getFunctionManager();
        Listing listing = currentProgram.getListing();

        try (
            PrintWriter output = new PrintWriter(
                new BufferedWriter(
                    new FileWriter(outputFile, StandardCharsets.UTF_8, false)
                )
            )
        ) {
            writeRow(output, "meta", "ghidra_version", Application.getApplicationVersion());
            writeRow(output, "meta", "program_name", currentProgram.getName());
            writeRow(output, "meta", "language_id", currentProgram.getLanguageID().toString());
            writeRow(
                output,
                "meta",
                "compiler_spec_id",
                currentProgram.getCompilerSpec().getCompilerSpecID().toString()
            );
            writeRow(output, "meta", "image_base", currentProgram.getImageBase().toString());

            for (int argumentIndex = 1; argumentIndex < args.length; argumentIndex++) {
                String argument = args[argumentIndex];
                int separator = argument.indexOf('=');
                String label;
                String addressText;
                if (separator > 0 && separator < argument.length() - 1) {
                    label = argument.substring(0, separator);
                    addressText = argument.substring(separator + 1);
                }
                else {
                    if (argumentIndex + 1 >= args.length) {
                        throw new IllegalArgumentException(
                            "invalid trailing boundary label: " + argument
                        );
                    }
                    label = argument;
                    addressText = args[++argumentIndex];
                }
                Address address = toAddr(addressText);
                if (address == null) {
                    throw new IllegalArgumentException("invalid address for " + label);
                }

                Function containing = functions.getFunctionContaining(address);
                if (containing == null) {
                    writeRow(output, "query", label, address.toString(), "no_function");
                }
                else {
                    AddressSetView body = containing.getBody();
                    writeRow(
                        output,
                        "query",
                        label,
                        address.toString(),
                        "function",
                        functionEntry(containing),
                        functionName(containing),
                        body.getMinAddress().toString(),
                        body.getMaxAddress().toString(),
                        Long.toString(body.getNumAddresses()),
                        bodySha256(body)
                    );

                    List<String> calls = new ArrayList<>();
                    InstructionIterator instructions = listing.getInstructions(body, true);
                    while (instructions.hasNext()) {
                        Instruction instruction = instructions.next();
                        if (!instruction.getFlowType().isCall()) {
                            continue;
                        }
                        for (Address target : instruction.getFlows()) {
                            Function targetFunction = functions.getFunctionAt(target);
                            calls.add(
                                instruction.getAddress() + "\t" + target + "\t" +
                                functionEntry(targetFunction) + "\t" + functionName(targetFunction)
                            );
                        }
                    }
                    Collections.sort(calls);
                    for (String call : calls) {
                        String[] fields = call.split("\t", -1);
                        writeRow(
                            output,
                            "call",
                            label,
                            fields[0],
                            fields[1],
                            fields[2],
                            fields[3]
                        );
                    }
                }

                List<String> references = new ArrayList<>();
                ReferenceIterator referenceIterator =
                    currentProgram.getReferenceManager().getReferencesTo(address);
                while (referenceIterator.hasNext()) {
                    Reference reference = referenceIterator.next();
                    Function source = functions.getFunctionContaining(reference.getFromAddress());
                    references.add(
                        reference.getFromAddress() + "\t" + reference.getReferenceType() + "\t" +
                        functionEntry(source) + "\t" + functionName(source)
                    );
                }
                Collections.sort(references);
                for (String reference : references) {
                    String[] fields = reference.split("\t", -1);
                    writeRow(
                        output,
                        "reference_to",
                        label,
                        fields[0],
                        fields[1],
                        fields[2],
                        fields[3]
                    );
                }
            }
        }

        println("Wrote boundary facts to " + outputFile);
    }
}
