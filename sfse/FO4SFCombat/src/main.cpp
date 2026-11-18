// FO4SFCombat: native hotkey bridge for CF-8 Combat Core (docs/combat/combat-core.md).
// Polls VatsKey (default 0x56 'V') and AmmoKey (default 0x4E 'N') while the game window is in front,
// and dispatches zero-argument static Papyrus calls on SFSE's main-thread TaskInterface through
// IVirtualMachine::DispatchStaticCall (slot 0x2F):
//   - FO4SF_CombatInput.OnVatsKey
//   - FO4SF_CombatInput.OnAmmoKey
//
// Built against libxse/commonlibsf 9d090c4 with the runtime pin, Address Library header check, RTTI checks,
// and vtable-bounds checks established by FOCCPing and FO4SFPipboyMenu.

#include "pch.h"

#include <array>
#include <atomic>
#include <cwchar>
#include <filesystem>
#include <format>
#include <fstream>
#include <string>
#include <string_view>
#include <vector>

#include "blocking_menus.h"

REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);

namespace
{
	using namespace std::string_view_literals;

	constexpr REL::Version kRuntime{ 1, 16, 244, 0 };
	constexpr std::size_t  kHeaderBytes = 96;               // Address Library format 5 header
	constexpr std::size_t  kGameVmImplAt = 0xE0;            // libxse RE::GameVM::impl (BSTSmartPointer<IVirtualMachine>)
	constexpr std::size_t  kDispatchStaticCallSlot = 0x2F;  // libxse IVirtualMachine::DispatchStaticCall

	struct Id
	{
		const char*   name;
		std::uint32_t id;
		const char*   source;
	};

	enum : std::size_t
	{
		kGameVmSingleton,
		kGameVmRtti,
		kVmRtti,
		kStringGetEntry,
		kStringRelease,
		kUiSingleton,
		kUiIsMenuOpen,
		kIdCount
	};

	constexpr std::array<Id, kIdCount> kIds{ {
		{ "GameVM.Singleton", 937585, "libxse" },
		{ "GameVM.RTTI", 865426, "libxse RTTI_GameVM" },
		{ "BSScript.Internal.VirtualMachine.RTTI", 870795, "libxse RTTI_BSScript__Internal__VirtualMachine" },
		{ "BSStringPool.GetEntry", 1186742, "libxse" },
		{ "BSStringPool.Entry.Release", 139340, "libxse" },
		{ "UI.Singleton", 937580, "libxse" },
		{ "UI.IsMenuOpen", 130475, "libxse" },
	} };

	std::uintptr_t                      g_base = 0;
	std::size_t                         g_imageSize = 0;
	std::array<std::uint32_t, kIdCount> g_rva{};
	const SFSE::TaskInterface*          g_task = nullptr;
	std::uint32_t                       g_vatsKey = 0x56;   // 'V'
	std::uint32_t                       g_ammoKey = 0x4E;   // 'N'
	bool                                g_gameVmOk = false;
	bool                                g_vmOff = false;
	std::uintptr_t                      g_checkedVm = 0;

	std::uintptr_t Address(std::size_t a_id) { return g_base + g_rva[a_id]; }

	bool InImage(std::uintptr_t a_addr, std::size_t a_len)
	{
		return a_addr >= g_base && a_len <= g_imageSize && a_addr - g_base <= g_imageSize - a_len;
	}

	std::string Hex(std::uintptr_t a_value) { return std::format("{:#x}", a_value); }

	bool Refuse(std::string_view a_step, const std::string& a_what)
	{
		REX::ERROR("refuse step={} {}", a_step, a_what);
		return false;
	}

	bool Peek(std::uintptr_t a_addr, void* a_out, std::size_t a_len)
	{
		__try {
			std::memcpy(a_out, reinterpret_cast<const void*>(a_addr), a_len);
			return true;
		} __except (1) {
			return false;
		}
	}

	bool LocatorOf(std::uintptr_t a_vtable, std::uint32_t& a_offset, std::uintptr_t& a_descriptor)
	{
		if (!InImage(a_vtable - 8, 8)) {
			return false;
		}
		const auto col = *reinterpret_cast<const std::uintptr_t*>(a_vtable - 8);
		if (!InImage(col, 0x14) || *reinterpret_cast<const std::uint32_t*>(col) != 1) {
			return false;
		}
		a_offset = *reinterpret_cast<const std::uint32_t*>(col + 0x04);
		a_descriptor = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x0C);
		return InImage(a_descriptor, 0x10);
	}

	bool CheckImage()
	{
		g_base = reinterpret_cast<std::uintptr_t>(REX::W32::GetModuleHandleW(nullptr));
		if (!g_base) {
			return Refuse("image", "reason=no_module");
		}
		const auto nt = g_base + *reinterpret_cast<const std::int32_t*>(g_base + 0x3C);
		if (*reinterpret_cast<const std::uint32_t*>(nt) != 0x00004550 ||
			*reinterpret_cast<const std::uint16_t*>(nt + 0x18) != 0x20B) {
			return Refuse("image", "reason=not_pe32plus");
		}
		g_imageSize = *reinterpret_cast<const std::uint32_t*>(nt + 0x18 + 0x38);
		REX::INFO("step=image base={} size={}", Hex(g_base), Hex(g_imageSize));
		return true;
	}

	bool ReadAddressLibrary(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		if (!in) {
			return Refuse("address_library", std::format("reason=missing file={}", a_file.filename().string()));
		}
		std::array<std::uint8_t, kHeaderBytes> head{};
		in.read(reinterpret_cast<char*>(head.data()), head.size());
		if (!in) {
			return Refuse("address_library", "reason=short_header");
		}
		const auto u32 = [&](std::size_t a_at) {
			std::uint32_t v;
			std::memcpy(&v, head.data() + a_at, sizeof v);
			return v;
		};
		const auto         format = u32(0);
		const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
			static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
		const auto         pointerSize = u32(84);
		const auto         count = u32(92);
		REX::INFO("step=address_library file={} format={} version={} pointer_size={} count={}", a_file.filename().string(),
			format, version.string(), pointerSize, count);
		if (format != 5 || version != kRuntime || pointerSize != 8) {
			return Refuse("address_library", "reason=header (format 5, version 1.16.244.0 and pointer size 8 expected)");
		}
		for (std::size_t i = 0; i < kIdCount; ++i) {
			const auto& id = kIds[i];
			if (id.id >= count) {
				return Refuse("id", std::format("name={} id={} reason=beyond_count count={}", id.name, id.id, count));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * id.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in) {
				return Refuse("id", std::format("name={} id={} reason=short_file", id.name, id.id));
			}
			if (!offset) {
				return Refuse("id", std::format("name={} id={} reason=missing", id.name, id.id));
			}
			if (offset >= g_imageSize) {
				return Refuse("id", std::format("name={} id={} rva={} reason=outside_image", id.name, id.id, Hex(offset)));
			}
			g_rva[i] = offset;
			REX::INFO("step=id name={} id={} rva={} source={}", id.name, id.id, Hex(offset), id.source);
		}
		for (std::size_t i = 0; i < kIdCount; ++i) {
			const auto viaLibrary = REL::ID(kIds[i].id).offset();
			if (viaLibrary != g_rva[i]) {
				return Refuse("id", std::format("name={} id={} reason=library_mismatch file={} libxse={}", kIds[i].name,
					kIds[i].id, Hex(g_rva[i]), Hex(viaLibrary)));
			}
		}
		return true;
	}

	bool ReadIniKey(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default, std::uint32_t& a_out)
	{
		std::array<wchar_t, 64> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFCombat", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		if (!text[0]) {
			a_out = a_default;
			return true;
		}
		wchar_t*   end = nullptr;
		const auto val = std::wcstoul(text.data(), &end, 0);
		if (end == text.data() || *end != L'\0' || val == 0 || val > 0xFE) {
			return false;
		}
		a_out = static_cast<std::uint32_t>(val);
		return true;
	}

	bool ReadConfig(const std::filesystem::path& a_ini)
	{
		if (!ReadIniKey(a_ini, L"VatsKey", 0x56, g_vatsKey) ||
			!ReadIniKey(a_ini, L"AmmoKey", 0x4E, g_ammoKey) ||
			g_vatsKey == g_ammoKey) {
			return Refuse("ini", "reason=invalid_key_config");
		}
		REX::INFO("step=ini vats_key={} ammo_key={}", Hex(g_vatsKey), Hex(g_ammoKey));
		return true;
	}

	bool CheckObject(std::string_view a_what, std::uintptr_t a_object, std::size_t a_rtti, std::uintptr_t& a_vtable)
	{
		std::uint32_t  offset = 0;
		std::uintptr_t descriptor = 0;
		if (!a_object || !Peek(a_object, &a_vtable, sizeof a_vtable) || !LocatorOf(a_vtable, offset, descriptor)) {
			return Refuse("object", std::format("name={} object={} reason=unreadable", a_what, Hex(a_object)));
		}
		if (descriptor != Address(a_rtti) || offset != 0) {
			return Refuse("object", std::format("name={} object={} reason=type offset={} type_descriptor={} rtti_id={}",
				a_what, Hex(a_object), Hex(offset), Hex(descriptor - g_base), Hex(g_rva[a_rtti])));
		}
		return true;
	}

	RE::BSScript::IVirtualMachine* ScriptVm()
	{
		if (g_vmOff) {
			return nullptr;
		}
		std::uintptr_t gameVm = 0;
		if (!Peek(Address(kGameVmSingleton), &gameVm, sizeof gameVm) || !gameVm) {
			return nullptr;
		}
		if (!g_gameVmOk) {
			std::uintptr_t gameVt = 0;
			if (!CheckObject("GameVM", gameVm, kGameVmRtti, gameVt)) {
				g_vmOff = true;
				return nullptr;
			}
			g_gameVmOk = true;
		}
		std::uintptr_t vm = 0;
		if (!Peek(gameVm + kGameVmImplAt, &vm, sizeof vm) || !vm) {
			return nullptr;
		}
		if (vm != g_checkedVm) {
			std::uintptr_t vt = 0;
			if (!CheckObject("VirtualMachine", vm, kVmRtti, vt) || !InImage(vt, (kDispatchStaticCallSlot + 1) * 8)) {
				g_vmOff = true;
				return nullptr;
			}
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			for (std::size_t i = 0; i <= kDispatchStaticCallSlot; ++i) {
				if (!InImage(slot[i], 1)) {
					g_vmOff = true;
					Refuse("object", std::format("name=VirtualMachine vtable={} slot={} reason=outside_image", Hex(vt), Hex(i)));
					return nullptr;
				}
			}
			g_checkedVm = vm;
			REX::INFO("step=object name=VirtualMachine object={} dispatch_static_call={}", Hex(vm),
				Hex(slot[kDispatchStaticCallSlot] - g_base));
		}
		return reinterpret_cast<RE::BSScript::IVirtualMachine*>(vm);
	}

	const char* OpenBlockingMenu()
	{
		return fo4sf::FindOpenBlockingMenu(RE::UI::GetSingleton(), false, true);
	}

	void DispatchCombatCall(const char* a_fn, std::uint32_t a_press)
	{
		if (const auto* menu = OpenBlockingMenu()) {
			REX::INFO("step=dispatch n={} fn=FO4SF_CombatInput.{} ignored=menu_open menu={}", a_press, a_fn, menu);
			return;
		}
		auto* const vm = ScriptVm();
		if (!vm) {
			REX::INFO("step=dispatch n={} fn=FO4SF_CombatInput.{} result=no_vm", a_press, a_fn);
			return;
		}
		const RE::BSFixedString                                        script("FO4SF_CombatInput");
		const RE::BSFixedString                                        function(a_fn);
		const RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> noCallback{};
		const auto noArguments = [](RE::BSScrapArray<RE::BSScript::Variable>&) { return true; };
		const bool queued = vm->DispatchStaticCall(script, function, noArguments, noCallback, 0);
		REX::INFO("step=dispatch n={} fn=FO4SF_CombatInput.{} queued={}", a_press, a_fn, queued ? 1 : 0);
	}

	bool GameInFront()
	{
		std::uint32_t pid = 0;
		W32_IMPL_GetWindowThreadProcessId(W32_IMPL_GetForegroundWindow(), &pid);
		return pid == W32_IMPL_GetCurrentProcessId();
	}

	std::uint32_t KeyThread(void*)
	{
		std::uint32_t vatsPresses = 0;
		std::uint32_t ammoPresses = 0;
		bool          vatsDown = false;
		bool          ammoDown = false;
		for (;;) {
			REX::W32::Sleep(30);
			const bool inFront = GameInFront();
			const bool vNow = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_vatsKey)) & 0x8000) != 0;
			if (vNow && !vatsDown && inFront) {
				const auto n = ++vatsPresses;
				g_task->AddTask([n]() { DispatchCombatCall("OnVatsKey", n); });
			}
			vatsDown = vNow;

			const bool aNow = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_ammoKey)) & 0x8000) != 0;
			if (aNow && !ammoDown && inFront) {
				const auto n = ++ammoPresses;
				g_task->AddTask([n]() { DispatchCombatCall("OnAmmoKey", n); });
			}
			ammoDown = aNow;
		}
	}

	void StartKeyWatcher()
	{
		const auto thread = REX::W32::CreateThread(nullptr, 0, &KeyThread, nullptr, 0, nullptr);
		if (!thread) {
			Refuse("key_thread", "reason=create_failed");
			return;
		}
		REX::W32::CloseHandle(thread);
		REX::INFO("step=key_thread vats_key={} ammo_key={}", Hex(g_vatsKey), Hex(g_ammoKey));
	}

	void OnMessage(SFSE::MessagingInterface::Message* a_msg)
	{
		if (a_msg && a_msg->type == SFSE::MessagingInterface::kPostDataLoad) {
			REX::INFO("step=post_data_load");
			g_task->AddTask([]() { StartKeyWatcher(); });
		}
	}
}

SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)
{
	SFSE::Init(a_sfse, { .trampoline = false, .hook = false });
	const auto runtime = a_sfse->RuntimeVersion();
	REX::INFO("FO4SFCombat loaded on runtime {}", runtime.string());

	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	std::array<wchar_t, 1024> path{};
	const auto len = REX::W32::GetModuleFileNameW(REX::W32::GetCurrentModule(), path.data(), static_cast<std::uint32_t>(path.size()));
	const auto dir = std::filesystem::path(std::wstring(path.data(), len)).parent_path();
	if (!CheckImage() || !ReadAddressLibrary(dir / "versionlib-1-16-244-0.bin") || !ReadConfig(dir / "FO4SFCombat.ini")) {
		return true;
	}
	const auto messaging = SFSE::GetMessagingInterface();
	g_task = SFSE::GetTaskInterface();
	if (!messaging || !g_task || !messaging->RegisterListener(&OnMessage)) {
		Refuse("listen", "reason=no_messaging_or_task_interface");
		return true;
	}
	REX::INFO("listening for PostDataLoad");
	return true;
}
