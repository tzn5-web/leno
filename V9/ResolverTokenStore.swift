import Foundation
import Security

enum ResolverTokenStore
{
    private static let service =
        "com.tzn5web.leno.v9.resolver"

    private static let account =
        "bearer-token"

    static func load()
        -> String
    {
        let query:
            [CFString: Any] = [
                kSecClass:
                    kSecClassGenericPassword,
                kSecAttrService:
                    service,
                kSecAttrAccount:
                    account,
                kSecReturnData:
                    true,
                kSecMatchLimit:
                    kSecMatchLimitOne
            ]

        var result:
            CFTypeRef?

        let status =
            SecItemCopyMatching(
                query as
                    CFDictionary,
                &result
            )

        guard status ==
                errSecSuccess,
              let data =
                result as?
                    Data,
              let value =
                String(
                    data:
                        data,
                    encoding:
                        .utf8
                )
        else {
            return ""
        }

        return value
    }

    static func save(
        _ value:
            String
    ) {
        let trimmed =
            value.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        let baseQuery:
            [CFString: Any] = [
                kSecClass:
                    kSecClassGenericPassword,
                kSecAttrService:
                    service,
                kSecAttrAccount:
                    account
            ]

        if trimmed.isEmpty {
            SecItemDelete(
                baseQuery as
                    CFDictionary
            )

            return
        }

        let data =
            Data(
                trimmed.utf8
            )

        let update:
            [CFString: Any] = [
                kSecValueData:
                    data,
                kSecAttrAccessible:
                    kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            ]

        let updateStatus =
            SecItemUpdate(
                baseQuery as
                    CFDictionary,
                update as
                    CFDictionary
            )

        if updateStatus ==
            errSecItemNotFound {
            var addQuery =
                baseQuery

            addQuery[
                kSecValueData
            ] =
                data

            addQuery[
                kSecAttrAccessible
            ] =
                kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

            SecItemAdd(
                addQuery as
                    CFDictionary,
                nil
            )
        }
    }
}
