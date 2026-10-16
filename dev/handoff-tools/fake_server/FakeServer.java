import java.io.*;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;

/**
 * Fake Minecraft-like server for testing the panel without a real server:
 * prints log lines like vanilla 1.21.1 and handles stop, list and say.
 * server.jar next to this file is built from it (any Java 8 or newer runs it):
 *   javac --release 8 FakeServer.java
 *   printf 'Main-Class: FakeServer\n' > manifest.txt
 *   jar cfm server.jar manifest.txt FakeServer*.class
 */
public class FakeServer {
    static final DateTimeFormatter F = DateTimeFormatter.ofPattern("HH:mm:ss");
    static void log(String level, String msg) {
        System.out.println("[" + LocalTime.now().format(F) + "] [Server thread/" + level + "]: " + msg);
        System.out.flush();
    }
    public static void main(String[] args) throws Exception {
        log("INFO", "Starting minecraft server version 1.21.1");
        log("INFO", "Loading properties");
        log("INFO", "Default game type: SURVIVAL");
        log("INFO", "Preparing level \"world\"");
        for (int p = 0; p <= 100; p += 25) { log("INFO", "Preparing spawn area: " + p + "%"); Thread.sleep(200); }
        log("INFO", "Done (1.234s)! For help, type \"help\"");
        Thread t = new Thread(() -> {
            int i = 0;
            while (true) {
                try { Thread.sleep(20000); } catch (InterruptedException e) { return; }
                i++;
                log("WARN", "Can't keep up! Is the server overloaded? Running 2" + i + "00ms or 4" + i + " ticks behind");
            }
        });
        t.setDaemon(true); t.start();
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String line;
        while ((line = in.readLine()) != null) {
            String cmd = line.trim();
            if (cmd.isEmpty()) continue;
            if (cmd.equals("stop")) { log("INFO", "Stopping the server"); log("INFO", "Saving worlds"); Thread.sleep(500); System.exit(0); }
            else if (cmd.equals("list")) log("INFO", "There are 0 of a max of 20 players online: ");
            else if (cmd.startsWith("say ")) log("INFO", "[Server] " + cmd.substring(4));
            else log("ERROR", "Unknown or incomplete command, see below for error: " + cmd + "<--[HERE]");
        }
    }
}
