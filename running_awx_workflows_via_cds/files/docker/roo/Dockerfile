FROM openjdk:8-jre-alpine
ENV lio_version 9.3.3
COPY lighty-community-*-bin.zip alpn-boot-*.jar starter.sh /

##libstdc++ is required by leveldbjni-1.8 (Akka dispatcher)
#Uncaught error from thread [opendaylight-cluster-data-akka.persistence.dispatchers.default-plugin-dispatcher-22]: Could not load library. Reasons: [no leveldbjni64-1.8 in java.library.path, no leveldbjni-1.8 in java.library.path, no leveldbjni in java.library.path, /tmp/libleveldbjni-64-1-3166161234556196376.8: Error loading shared library libstdc++.so.6: No such file or directory (needed by /tmp/libleveldbjni-64-1-3166161234556196376.8)], shutting down JVM since 'akka.jvm-exit-on-fatal-error' is enabled for ActorSystem[opendaylight-cluster-data]
RUN unzip /lighty-community-*-bin.zip \
    && rm /lighty-community-*-bin.zip \
    && apk update \
    && apk add --no-cache curl openssh-server python2 iproute2 \
    && sed -i /etc/ssh/sshd_config \
        -e '/PermitRootLogin/s/^.*$/PermitRootLogin yes/' \
        -e '/PermitEmptyPasswords/s/^.*$/PermitEmptyPasswords yes/' 

EXPOSE 8888
EXPOSE 8185
EXPOSE 6633
EXPOSE 6653
EXPOSE 2550
EXPOSE 80
EXPOSE 22

CMD /starter.sh
