# Təhlükəsiz sahib/admin quraşdırılması

Mövcud Django saytı, müştəri hesabları və dizayn saxlanılıb. Heç bir hazır admin şifrəsi yoxdur. `createsuperuser` ilə yaradılmış hesab belə sahibin təsdiq qeydi olmadan bu saytın admin panelinə buraxılmır. İlk sahibin yaradılması yalnız aşağıdakı qorunan axınla edilir.

## 1. Render-də private Environment dəyişənləri

Bu məlumatları **Render → farmcart → Environment** bölməsinə daxil edin. Şifrələri, API açarlarını, setup açarını və təsdiq kodlarını çata, GitHub-a və ekran görüntülərinə qoymayın.

| Dəyişən | Təyinat |
| --- | --- |
| `OWNER_EMAIL` | Yalnız sizə məxsus Gmail ünvanı, `@gmail.com` ilə bitməlidir. Formada başqa alıcı seçilə bilməz. |
| `EMAIL_API_KEY` | Resend hesabının məktub göndərmə API açarı. Yalnız serverdə saxlanır. |
| `EMAIL_FROM` | Resend-in icazə verdiyi göndərən. Öz Gmail ünvanınızı təsadüfi göndərən kimi yazmayın. |
| `ADMIN_SETUP_SECRET` | Ən azı 32 simvolluq təsadüfi, bu quraşdırmaya məxsus gizli açar. Parol menecerinin təsadüfi generatorundan istifadə edə bilərsiniz. |
| `DATABASE_URL` | Qalıcı PostgreSQL bazasının TLS bağlantısı. Render-in pulsuz serverindəki `/tmp` bazası sahib qeydini qorumaq üçün uyğun deyil. |
| `DJANGO_SECRET_KEY` | Mövcud Render gizli Django açarını dəyişmədən saxlayın. |
| `CLOUDINARY_CLOUD_NAME` | Şəkil/video üçün Cloudinary hesabının cloud name məlumatı. |
| `CLOUDINARY_API_KEY` | Cloudinary API açarı. |
| `CLOUDINARY_API_SECRET` | Cloudinary API sirri. |

Resend HTTPS API vasitəsilə işləyir; SMTP portu tələb etmir. Resend hesabını `OWNER_EMAIL` kimi istifadə etdiyiniz Gmail ilə açsanız, provayderin sınaq göndərəni `FarmCart <onboarding@resend.dev>` yalnız həmin hesab ünvanına göndərmə üçün yararlı ola bilər. Provayderin panelindəki aktual sender/recipient icazələrini yoxlayın. Digər göndərən üçün Resend-də həmin domenin təsdiqi lazımdır. Kodlar və yeni admin təsdiqləri hər halda yalnız `OWNER_EMAIL` ünvanına gedir.

Render web serveri **Free** planında qalır; bu dəyişiklik heç bir ödənişli Render bazası/disk yaratmır. Qalıcı PostgreSQL və Cloudinary üçün öz hesablarınızı qoşmalısınız; onların pulsuz planları və limitləri həmin xidmətlərin şərtlərindən asılıdır. Burada həmin xarici hesablar yaradılmayıb və real bağlantı yoxlanılmayıb.

**Mövcud məlumatları qoruyun:** `DATABASE_URL` əlavə etməzdən və ya storage dəyişməzdən əvvəl mövcud bazanın və yükləmələrin ehtiyat nüsxəsini alın. Yeni boş PostgreSQL bazasına qoşulmaq köhnə SQLite məlumatlarını avtomatik daşımır. Pulsuz Render-in müvəqqəti diski redeploy zamanı itə bilər. Bu səbəbdən bu dəyişikliklər əvvəlcə ayrıca Git branch-də hazırlanır; backup/config tamamlanmadan canlı xidməti dəyişməyin. İxrac/idxalı yalnız etibarlı operator etsin. Şəxsi database export fayllarını Git-ə əlavə etməyin.

Etibarlı operator üçün köçürmə ardıcıllığı: köhnə bazadan Django `dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission` ilə private ixrac, upload fayllarının ayrıca ehtiyat nüsxəsi, yeni PostgreSQL-də `migrate`, sonra private `loaddata`. Eyni sabit `DJANGO_SECRET_KEY` saxlanmalıdır. Cloudinary-yə keçməzdən əvvəl mövcud yerli faylları uyğun image/video resource növləri ilə köçürüb bazadakı fayl adlarını yoxlamaq lazımdır; yalnız dəyişənləri dəyişmək köhnə faylları Cloudinary-yə yükləmir. Bu köçürmə uzaq serverə giriş olmadan avtomatik icra edilmir.

## 2. İlk sahib hesabı

1. Konfiqurasiya və migrations tamamlandıqdan sonra saytın **`/admin/setup/`** səhifəsini açın.
2. Serverdə yaratdığınız `ADMIN_SETUP_SECRET` açarını yazın.
3. Öz admin istifadəçi adınızı və güclü şifrənizi yaradın. İstifadəçi adı sahəsində `umid_w` ilkin təklifdir; şifrə heç vaxt əvvəlcədən təyin edilmir.
4. Kod göndər düyməsini basın. Heç bir hesab bu anda aktivləşmir.
5. Yalnız serverdəki `OWNER_EMAIL` Gmail-inə gələn **8 rəqəmli kodu** 10 dəqiqə ərzində daxil edin və təsdiq xanasını seçin.
6. Təsdiqdən sonra **`/admin/login/`** səhifəsində yaratdığınız istifadəçi adı və şifrə ilə daxil olun.
7. `ADMIN_SETUP_SECRET` dəyişənini Render-dən silin. Baza quraşdırmanın bitdiyini ayrıca saxlayır: açar qalsa və ya sonradan dəyişdirilsə belə ictimai setup yenidən açılmır; `/admin/setup/` HTTP 404 qaytarır.

Məktub çatmasa resend etmək üçün setup formasına qayıtmaq olar; əvvəlki eyni tip kod etibarsız olur. Göndərmə hər əməliyyat növü üzrə saatda 3 dəfə, sorğular mənbə üzrə 15 dəqiqədə 10 dəfə məhduddur. Kod başına maksimum 5 cəhd var. Limitlər bazada saxlanır və server prosesi yenidən başlayanda sıfırlanmır. Backend səviyyəsində bir singleton qeyd və atomik əməliyyat ilkin sahibin paralel sorğularla iki dəfə yaradılmasının qarşısını alır.

Sahib Gmail-i təsdiqdən sonra serverdə təsadüfi dəyişdirilərsə, gözləyən kodlar etibarsız olur və əlavə admin/bərpa axınları bağlanır. Gmail dəyişməsi sadə müştəri profili vasitəsilə edilmir; gələcək dəyişmə etibarlı operator tərəfindən ayrıca təsdiqlənmiş miqrasiya tələb edir.

### Şifrəni təhlükəsiz lokal terminalda təyin etmək

Eyni bir dəfəlik quraşdırmanı brauzer əvəzinə öz serverinizin interaktiv terminalında da başlada bilərsiniz:

```bash
python manage.py initialize_owner
```

Lokal layihədə virtual mühiti aktivləşdirməmisinizsə, Linux/macOS üçün `.venv/bin/python manage.py initialize_owner`, Windows üçün `.venv\Scripts\python.exe manage.py initialize_owner` istifadə edin. Hosting terminalında yuxarıdakı `python` əmri uyğundur.

İstifadəçi adı üçün Enter basmaq `umid_w` seçir. Setup açarı, yeni şifrə, şifrə təkrarı və Gmail kodu gizli terminal sorğuları ilə daxil edilir. Şifrə/kod komanda arqumenti kimi qəbul edilmir, ekrana çap edilmir və shell tarixçəsinə yazılmır. Boru (`pipe`) ilə qeyri-interaktiv giriş rədd edilir. E-poçt təsdiqindən əvvəl hesab yaranmır; əvvəl quraşdırılmış sahib varsa, əmr bloklanır. Bu üsul da yuxarıdakı private e-poçt və qalıcı baza konfiqurasiyasını tələb edir. Render Free-də terminal yoxdursa brauzer axınından istifadə edin.

## 3. Əlavə admin, icazələrin ləğvi və şifrə bərpası

- Sahib admin panelinin ana səhifəsində **Əlavə administrator yarat** keçidini görür. `/admin/owner/administrators/` yalnız təsdiqlənmiş sahibə açıqdır.
- Sahib öz cari şifrəsini yenidən yazır, əlavə hesab üçün istifadəçi adı/şifrə seçir və sorğunu başlayır.
- Təsdiq yalnız sahib Gmail-inə göndərilir. Kod və açıq təsdiq olmadan əlavə hesab yaranmır. Əlavə admin superuser deyil; yalnız mağaza məzmunu üçün icazələr alır.
- Eyni qorunan səhifədə sahib cari şifrəsini yenidən yazıb təsdiq etməklə əlavə adminin icazəsini ləğv edə bilər. Həmin hesab dərhal admin panelinə girişini itirir.
- Müştəri siyahısı admin panelində yalnız oxumaq üçündür. Oradan user/staff/superuser rolları dəyişdirilə, əlavə admin yaradıla və qruplarla dolayı icazə verilə bilməz.
- **`/admin/recover/`** ünvanında təsdiqlənmiş adminin istifadəçi adını və yeni şifrəni yazın. Cavab hesabın mövcudluğunu açıqlamır. Bərpa kodu həmişə yalnız sahib Gmail-inə gedir. Təsdiq edilənə qədər köhnə şifrə dəyişmir. Şifrə dəyişdikdə əvvəlki autentifikasiya sessiyaları etibarsız olur.
- Admin girişinə limit qoyulub və admin sessiyası 30 dəqiqəlikdir. HTTPS, secure/HttpOnly sessiya cookies, CSRF, təkrar şifrə yoxlaması və backend rol yoxlamaları saxlanılıb.

## 4. Mağaza idarəetməsi və Reels

- **Products:** əlavə et/dəyiş/sil; ad və təsvirlər iki dildədir. Qiymət, faiz endirimi, stok və şəkilləri dəyişmək olur. Məhsulun içindəki variant sətirlərində və ayrıca **Product variants** bölməsində çəki/ad, ayrıca qiymət və stok təyin edilir; variantların ayrıca təsdiqli silinməsi də mövcuddur. Boş stok “saytdan kənar izlənir”, `0` isə “bitib” deməkdir. Məhsul səviyyəsində stok verilərsə, bütün variantlar üçün ümumi limitdir.
- **Regions / Categories:** əlavə et/dəyiş/sil. Məhsulu olan bölgə/kateqoriya silinməzdən əvvəl məhsulları başqa yerə keçirmək tələb olunur; təsadüfi məhsul itkisi olmur.
- **Videos → Add:** başlıqları yazın, MP4/WebM/MOV faylını seçin, məhsulu əlaqələndirin, **Reels** və **Active** işarələrini seçin, **Position** ilə sıralayın, saxlayın. MP4 üçün browser-compatible H.264 tövsiyə olunur. Mövcud videoda Replace/Delete, playback preview və təsdiqli silmə işləyir.
- Şəkil limiti 10 MB, video limiti 100 MB-dır; providerin ayrıca limitləri də tətbiq olunur. Render-də qalıcı Cloudinary qoşulmayıbsa upload forması faylın itə biləcəyi müvəqqəti diskə yazmağa icazə vermir və izah göstərir. Storage bağlantısı xətaları istifadəçiyə ümumi, anlaşılan mesajla qaytarılır; açarlar və provider cavabları göstərilmir.
- **Store configuration:** WhatsApp, telefon, Instagram adı/URL, biznes adı, logo, e-poçt və ünvan dəyişdirilir. Məlumatları ayrı-ayrılıqda silmək və ya Store configuration qeydini təsdiqlə tam silib yenisini yaratmaq olar; bu halda kontaktlar boş görünür və WhatsApp sifarişi yeni nömrə yazılana qədər deaktiv olur. İstənilən ilkin kontaktlar miqrasiya ilə qoyulur: WhatsApp `+994772506587`, telefon `077 250 65 87`, Instagram `l.umidw`.
- Səbət variant/çəki, miqdar, endirimli vahid qiymət və toplamı serverdə hesablayır. Çatdırılma forması ad, telefon, ünvan və qeyd əlavə edir. WhatsApp düyməsi xülasəni açır; müştəri **Send** düyməsini özü basır. Avtomatik mesaj göndərilmir, stok WhatsApp linki açıldığına görə azaldılmır və rezerv edilmir; satışı sahib təsdiqləyəndə stok admin panelindən yenilənir.

## 5. Yoxlama

Operator üçün:

```bash
python manage.py migrate
python manage.py check
python manage.py check_owner_auth
python manage.py test
```

`check_owner_auth` yalnız dəyişən adları və mövcudluğunu yoxlayır, məktub göndərmir və sirr dəyərlərini çap etmir. `prune_admin_challenges` köhnə kod materialını və köhnə limit qeydlərini təmizləyir; Render startup onu işə salır.

Əl ilə tam yoxlama:

1. Gizli açarsız ilk setup sorğusunu yoxlayın: hesab və məktub yaranmamalıdır.
2. Düzgün setup açarı ilə hesab məlumatlarını göndərin; yalnız öz təyin edilmiş Gmail-inizdə məktubun gəldiyini yoxlayın.
3. Səhv kodu yoxlayın, sonra düzgün kodu təsdiqləyin. 10 dəqiqəsi keçmiş və ya 5 cəhdi bitmiş kod rədd edilməlidir. Bir neçə fərqli pending kod göndərərkən rate limitləri nəzərə alın.
4. `/admin/login/` ilə daxil olun; setup səhifəsinin artıq 404 qaytardığını yoxlayın.
5. Adi müştəri hesabı ilə admin və əlavə admin yaratma ünvanlarına girməyin rədd edildiyini yoxlayın.
6. Sahib olaraq əlavə admin sorğusunu cari şifrə + Gmail kodu ilə təsdiqləyin. Əlavə admin mağazanı idarə edə bilməli, əlavə admin yaratmağa və rolları dəyişməyə icazəsi olmamalıdır.
7. `/admin/recover/` axını ilə şifrəni bərpa edin, kodun başqa alıcıya göndərilə bilmədiyini yoxlayın.
8. Serveri yenidən başladın: qalıcı bazada sahib və bağlanmış setup vəziyyəti saxlanmalıdır. Məhsul və Reels yükləmələrinin də yenidən görünməsini yoxlayın.

Avtomatlaşdırılmış testlər sınaq məktub qutusundan istifadə edir; onlar həqiqi Gmail-ə məktub göndərmir. Kod təsdiqi, səhv/vaxtı keçmiş/təkrar kodlar, limitlər, paralel setup, istifadəçi rolları, bərpa, admin approval, stok/variantlar, WhatsApp və media axınları yoxlanılır. Ayrıca browser yoxlaması həqiqi lokal MP4 playback və idarəetmə axınlarını icra edir. Canlı Resend, PostgreSQL və Cloudinary bağlantıları yalnız sizin konfiqurasiyanız verildikdən sonra yoxlanıla bilər; hazırda aktiv sayılmır.
