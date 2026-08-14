# Third-Party License Records

Structured-text backend parser dependencies. Both artifacts are
distributed under the Apache License 2.0.

| Artifact | Version | License | Artifact URL |
|---|---|---|---|
| com.google.code.gson:gson | 2.13.2 | Apache-2.0 | https://repo1.maven.org/maven2/com/google/code/gson/gson/2.13.2/gson-2.13.2.jar |
| org.apache.commons:commons-csv | 1.10.0 | Apache-2.0 | https://repo1.maven.org/maven2/org/apache/commons/commons-csv/1.10.0/commons-csv-1.10.0.jar |
| org.apache.commons:commons-lang3 | 3.12.0 | Apache-2.0 | https://repo1.maven.org/maven2/org/apache/commons/commons-lang3/3.12.0/commons-lang3-3.12.0.jar |

Note: the plan originally pinned commons-csv 1.14.1. Versions >= 1.11.0
hard-require commons-io 2.x at class load, and commons-io 2.x is unreachable
from every configured mirror (404 on Central, Aliyun, Huawei, Tencent,
Google). commons-csv 1.10.0 provides the same parser/printer API surface
used by the codec and has no unavailable runtime dependencies. See the SDD
ledger ruling.

Full license texts:
- gson: https://www.apache.org/licenses/LICENSE-2.0.txt
- commons-csv: https://www.apache.org/licenses/LICENSE-2.0.txt
