import com.slgtranslator.app.RenPyRpycParser;
import java.nio.file.Files;
import java.nio.file.Paths;

public final class ParserSmokeTest {
    public static void main(String[] args) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        String result = RenPyRpycParser.INSTANCE.parseRpyc(data);
        int strings = 0;
        for (String line : result.split("\\n")) {
            if (line.startsWith("RPYC_STRING\t")) strings++;
            if (line.startsWith("RPYC_DIAG\t")) System.out.println(line);
        }
        System.out.println("RPYC_STRING count=" + strings);
        String expected = args.length > 1 ? args[1] : "Damn it! I've been walking for six hours";
        if (!result.contains(expected)) {
            throw new AssertionError("Expected text was not extracted: " + expected);
        }
    }
}
