/* ==========================================================================
   QWebChannel istemcisi — Qt 5 tel protokolüne (wire protocol) uyumlu.

   ⚠️ ÖNCEKİ SÜRÜM BOZUKTU: mesaj tipi numaraları uydurmaydı (init=4, response=2,
   invokeMethod=5). Qt 5'te init=3, response=10, invokeMethod=6. Yanlış numara
   yüzünden Qt "init" isteğini hiç cevaplamıyor, initCallback tetiklenmiyor ve
   window.pybridge asla oluşmuyordu → tüm butonlar "simüle edildi" dalına düşüyordu.

   Bu dosya görsel hiçbir şeye dokunmaz; sadece JS ↔ Python haberleşmesidir.
   ========================================================================== */

"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10
};

var QWebChannel = function (transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("QWebChannel bir transport nesnesi bekler, gelen: " + typeof transport);
        return;
    }

    var channel = this;
    this.transport = transport;
    this.objects = {};
    this.execCallbacks = {};
    this.execId = 0;

    this.send = function (data) {
        if (typeof data !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    };

    this.transport.onmessage = function (message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("Geçersiz QWebChannel mesajı:", message.data);
                break;
        }
    };

    this.exec = function (data, callback) {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_SAFE_INTEGER) {
            channel.execId = Number.MIN_SAFE_INTEGER;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Gönderilecek veride zaten id var:", data);
            return;
        }
        data.id = channel.execId++;
        channel.execCallbacks[data.id] = callback;
        channel.send(data);
    };

    this.handleSignal = function (message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Bilinmeyen nesneden sinyal geldi: " + message.object);
        }
    };

    this.handleResponse = function (message) {
        if (!message.hasOwnProperty("id")) {
            console.error("id'siz cevap geldi:", message);
            return;
        }
        var callback = channel.execCallbacks[message.id];
        delete channel.execCallbacks[message.id];
        if (callback) {
            callback(message.data);
        }
    };

    this.handlePropertyUpdate = function (message) {
        for (var i = 0; i < message.data.length; ++i) {
            var data = message.data[i];
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Bilinmeyen nesne için property güncellemesi: " + data.object);
            }
        }
        channel.exec({ type: QWebChannelMessageTypes.idle });
    };

    this.debug = function (message) {
        channel.send({ type: QWebChannelMessageTypes.debug, data: message });
    };

    // --- Handshake: nesne listesini iste -----------------------------------
    channel.exec({ type: QWebChannelMessageTypes.init }, function (data) {
        for (var objectName in data) {
            new QObject(objectName, data[objectName], channel);
        }
        // Diğer nesnelere referans veren property'leri çöz
        for (var name in channel.objects) {
            channel.objects[name].unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({ type: QWebChannelMessageTypes.idle });
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;

    var object = this;
    var propertyCache = {};       // property index -> değer
    var objectSignals = {};       // signal index  -> callback dizisi

    function unwrapQObject(response) {
        if (response instanceof Array) {
            var result = [];
            for (var i = 0; i < response.length; ++i) {
                result.push(unwrapQObject(response[i]));
            }
            return result;
        }
        if (!response || !response["__QObject*__"] || response.id === undefined) {
            return response;
        }
        var objectId = response.id;
        if (webChannel.objects[objectId]) {
            return webChannel.objects[objectId];
        }
        if (!response.data) {
            console.error("QObject çözülemedi, veri yok:", response);
            return;
        }
        var qObject = new QObject(objectId, response.data, webChannel);
        if (qObject.destroyed) {
            qObject.destroyed.connect(function () {
                if (webChannel.objects[objectId] === qObject) {
                    delete webChannel.objects[objectId];
                }
            });
        }
        return qObject;
    }

    this.unwrapProperties = function () {
        for (var propertyIdx in propertyCache) {
            propertyCache[propertyIdx] = unwrapQObject(propertyCache[propertyIdx]);
        }
    };

    function addSignal(signalData, isPropertyNotifySignal) {
        var signalName = signalData[0];
        var signalIndex = signalData[1];

        object[signalName] = {
            connect: function (callback) {
                if (typeof callback !== "function") {
                    console.error("'" + signalName + "' sinyaline geçersiz callback verildi.");
                    return;
                }
                objectSignals[signalIndex] = objectSignals[signalIndex] || [];
                objectSignals[signalIndex].push(callback);

                // Property notify sinyalleri ve 'destroyed' zaten sunucu tarafından
                // gönderilir; diğerleri için abonelik isteği yollanmalı.
                if (!isPropertyNotifySignal && signalName !== "destroyed") {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.connectToSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            },
            disconnect: function (callback) {
                if (typeof callback !== "function") {
                    console.error("'" + signalName + "' bağlantısı için geçersiz callback.");
                    return;
                }
                var idx = (objectSignals[signalIndex] || []).indexOf(callback);
                if (idx === -1) {
                    console.error("Bağlı olmayan bir callback koparılmaya çalışıldı.");
                    return;
                }
                objectSignals[signalIndex].splice(idx, 1);
                if (!isPropertyNotifySignal && objectSignals[signalIndex].length === 0) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            }
        };
    }

    function invokeSignalCallbacks(signalName, signalArgs) {
        var connections = objectSignals[signalName];
        if (connections) {
            connections.forEach(function (callback) {
                callback.apply(callback, signalArgs);
            });
        }
    }

    this.propertyUpdate = function (signals, propertyMap) {
        for (var propertyIndex in propertyMap) {
            propertyCache[propertyIndex] = propertyMap[propertyIndex];
        }
        for (var signalName in signals) {
            invokeSignalCallbacks(signalName, signals[signalName]);
        }
    };

    this.signalEmitted = function (signalName, signalArgs) {
        invokeSignalCallbacks(signalName, unwrapQObject(signalArgs));
    };

    function addMethod(methodData) {
        var methodName = methodData[0];
        var methodIdx = methodData[1];

        object[methodName] = function () {
            var args = [];
            var callback;
            for (var i = 0; i < arguments.length; ++i) {
                var argument = arguments[i];
                if (typeof argument === "function") {
                    callback = argument;
                } else if (argument instanceof QObject && webChannel.objects[argument.__id__] !== undefined) {
                    args.push({ id: argument.__id__ });
                } else {
                    args.push(argument);
                }
            }

            // Metot indeksiyle çağırıyoruz: tüm Qt 5 sürümleri indeksi kabul eder.
            webChannel.exec({
                type: QWebChannelMessageTypes.invokeMethod,
                object: object.__id__,
                method: methodIdx,
                args: args
            }, function (response) {
                if (response !== undefined) {
                    var result = unwrapQObject(response);
                    if (callback) {
                        callback(result);
                    }
                } else if (callback) {
                    callback(undefined);
                }
            });
        };
    }

    function bindGetterSetter(propertyInfo) {
        var propertyIndex = propertyInfo[0];
        var propertyName = propertyInfo[1];
        var notifySignalData = propertyInfo[2];
        var propertyValue = propertyInfo[3];

        // notifySignalData[0] === 1 → property değişim sinyali (isim yok)
        if (notifySignalData) {
            if (notifySignalData[0] === 1) {
                notifySignalData[0] = propertyName + "Changed";
            }
            addSignal(notifySignalData, true);
        }
        propertyCache[propertyIndex] = propertyValue;

        Object.defineProperty(object, propertyName, {
            configurable: true,
            get: function () {
                var value = propertyCache[propertyIndex];
                if (value === undefined) {
                    console.warn('"' + propertyName + '" property değeri bilinmiyor.');
                    return;
                }
                return value;
            },
            set: function (value) {
                if (value === undefined) {
                    console.warn('"' + propertyName + '" property\'sine undefined atanamaz.');
                    return;
                }
                propertyCache[propertyIndex] = value;
                var valueToSend = value;
                if (valueToSend instanceof QObject && webChannel.objects[valueToSend.__id__] !== undefined) {
                    valueToSend = { id: valueToSend.__id__ };
                }
                webChannel.exec({
                    type: QWebChannelMessageTypes.setProperty,
                    object: object.__id__,
                    property: propertyIndex,
                    value: valueToSend
                });
            }
        });
    }

    (data.methods || []).forEach(addMethod);
    (data.properties || []).forEach(bindGetterSetter);
    (data.signals || []).forEach(function (signal) { addSignal(signal, false); });

    for (var enumName in (data.enums || {})) {
        object[enumName] = data.enums[enumName];
    }
}
