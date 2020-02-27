for key in rsa dsa ecdsa ed25519 ; do
    path=/etc/ssh/ssh_host_${key}_key
    [ -f $path ] || ssh-keygen -f $path -t $key -P ''
done
/usr/sbin/sshd &
cd lighty-community-*/
java -Xbootclasspath/p:/alpn-boot-*.jar -jar lighty-community-*.jar sampleConfigSingleNode.json
