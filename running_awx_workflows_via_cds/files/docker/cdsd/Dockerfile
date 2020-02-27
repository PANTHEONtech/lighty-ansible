FROM nexus3.onap.org:10001/onap/ccsdk-blueprintsprocessor:0.7.0-STAGING-latest

RUN sed -i -e '$s/^/-agentlib:jdwp=transport=dt_socket,address=8111,server=y,suspend=n /' startService.sh \
    && sed -i /opt/app/onap/config/application.properties \
        -e '/blueprintsprocessor.loadBluePrintPaths/s:blueprint-model.*$:blueprint-model/service-blueprint:' \
        -e '/blueprintsprocessor.loadModeTypePaths/s:definition-type.*$:definition-type/starter-type:' \
        -e '/blueprintsprocessor.loadResourceDictionaryPaths/s:resource-dictionary.*$:resource-dictionary/starter-dictionary:'

EXPOSE 8111
