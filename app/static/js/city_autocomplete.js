// Ukrainian locations autocomplete
// Dataset: { name, region, type }
// type: 'місто' | 'смт' | 'селище' | 'село'

const _rawLocations = [
  // ── Київ (завжди перший) ──────────────────────────────────────────────────
  { name: 'Київ',                   region: 'Київська',           type: 'місто'   },

  // ── Обласні центри ───────────────────────────────────────────────────────
  { name: 'Харків',                 region: 'Харківська',         type: 'місто'   },
  { name: 'Одеса',                  region: 'Одеська',            type: 'місто'   },
  { name: 'Дніпро',                 region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Запоріжжя',              region: 'Запорізька',         type: 'місто'   },
  { name: 'Львів',                  region: 'Львівська',          type: 'місто'   },
  { name: 'Кривий Ріг',             region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Миколаїв',               region: 'Миколаївська',       type: 'місто'   },
  { name: 'Вінниця',                region: 'Вінницька',          type: 'місто'   },
  { name: 'Херсон',                 region: 'Херсонська',         type: 'місто'   },
  { name: 'Полтава',                region: 'Полтавська',         type: 'місто'   },
  { name: 'Чернігів',               region: 'Чернігівська',       type: 'місто'   },
  { name: 'Черкаси',                region: 'Черкаська',          type: 'місто'   },
  { name: 'Суми',                   region: 'Сумська',            type: 'місто'   },
  { name: 'Хмельницький',           region: 'Хмельницька',        type: 'місто'   },
  { name: 'Житомир',                region: 'Житомирська',        type: 'місто'   },
  { name: 'Рівне',                  region: 'Рівненська',         type: 'місто'   },
  { name: 'Тернопіль',              region: 'Тернопільська',      type: 'місто'   },
  { name: 'Івано-Франківськ',       region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Луцьк',                  region: 'Волинська',          type: 'місто'   },
  { name: 'Ужгород',                region: 'Закарпатська',       type: 'місто'   },
  { name: 'Чернівці',               region: 'Чернівецька',        type: 'місто'   },
  { name: 'Кропивницький',          region: 'Кіровоградська',     type: 'місто'   },
  { name: 'Луганськ',               region: 'Луганська',          type: 'місто'   },
  { name: 'Донецьк',                region: 'Донецька',           type: 'місто'   },

  // ── Київська область ─────────────────────────────────────────────────────
  { name: 'Біла Церква',            region: 'Київська',           type: 'місто'   },
  { name: 'Бориспіль',              region: 'Київська',           type: 'місто'   },
  { name: 'Бровари',                region: 'Київська',           type: 'місто'   },
  { name: 'Буча',                   region: 'Київська',           type: 'місто'   },
  { name: 'Васильків',              region: 'Київська',           type: 'місто'   },
  { name: 'Вишгород',               region: 'Київська',           type: 'місто'   },
  { name: 'Ірпінь',                 region: 'Київська',           type: 'місто'   },
  { name: 'Обухів',                 region: 'Київська',           type: 'місто'   },
  { name: 'Переяслав',              region: 'Київська',           type: 'місто'   },
  { name: 'Фастів',                 region: 'Київська',           type: 'місто'   },
  { name: 'Яготин',                 region: 'Київська',           type: 'місто'   },
  { name: 'Боярка',                 region: 'Київська',           type: 'смт'     },
  { name: 'Вишневе',                region: 'Київська',           type: 'смт'     },
  { name: 'Ворзель',                region: 'Київська',           type: 'смт'     },
  { name: 'Гостомель',              region: 'Київська',           type: 'смт'     },
  { name: 'Калинівка',              region: 'Київська',           type: 'смт'     },
  { name: 'Коцюбинське',            region: 'Київська',           type: 'смт'     },
  { name: 'Українка',               region: 'Київська',           type: 'смт'     },
  { name: 'Бориспіль',              region: 'Київська',           type: 'місто'   },
  { name: 'Баришівка',              region: 'Київська',           type: 'смт'     },
  { name: 'Березань',               region: 'Київська',           type: 'місто'   },
  { name: 'Бородянка',              region: 'Київська',           type: 'смт'     },
  { name: 'Броварі',                region: 'Київська',           type: 'смт'     },
  { name: 'Вишнева',                region: 'Київська',           type: 'смт'     },
  { name: 'Глеваха',                region: 'Київська',           type: 'смт'     },
  { name: 'Здолбунів',              region: 'Рівненська',         type: 'місто'   },
  { name: 'Іванків',                region: 'Київська',           type: 'смт'     },
  { name: 'Кагарлик',               region: 'Київська',           type: 'місто'   },
  { name: 'Макарів',                region: 'Київська',           type: 'смт'     },
  { name: 'Миронівка',              region: 'Київська',           type: 'місто'   },
  { name: 'Переяслав-Хмельницький', region: 'Київська',           type: 'місто'   },
  { name: 'Ржищів',                 region: 'Київська',           type: 'місто'   },
  { name: 'Рокитне',                region: 'Київська',           type: 'смт'     },
  { name: 'Сквира',                 region: 'Київська',           type: 'місто'   },
  { name: 'Славутич',               region: 'Київська',           type: 'місто'   },
  { name: 'Тараща',                 region: 'Київська',           type: 'місто'   },
  { name: 'Тетіїв',                 region: 'Київська',           type: 'місто'   },
  { name: 'Узин',                   region: 'Київська',           type: 'смт'     },
  { name: 'Ірпінь',                 region: 'Київська',           type: 'місто'   },

  // ── Харківська область ───────────────────────────────────────────────────
  { name: 'Балаклія',               region: 'Харківська',         type: 'місто'   },
  { name: 'Богодухів',              region: 'Харківська',         type: 'місто'   },
  { name: 'Валки',                  region: 'Харківська',         type: 'місто'   },
  { name: 'Дергачі',                region: 'Харківська',         type: 'смт'     },
  { name: 'Зміїв',                  region: 'Харківська',         type: 'місто'   },
  { name: 'Ізюм',                   region: 'Харківська',         type: 'місто'   },
  { name: 'Красноград',             region: 'Харківська',         type: 'місто'   },
  { name: 'Куп\'янськ',             region: 'Харківська',         type: 'місто'   },
  { name: 'Лозова',                 region: 'Харківська',         type: 'місто'   },
  { name: 'Люботин',                region: 'Харківська',         type: 'місто'   },
  { name: 'Мерефа',                 region: 'Харківська',         type: 'місто'   },
  { name: 'Первомайський',          region: 'Харківська',         type: 'місто'   },
  { name: 'Чугуїв',                 region: 'Харківська',         type: 'місто'   },

  // ── Одеська область ──────────────────────────────────────────────────────
  { name: 'Ізмаїл',                 region: 'Одеська',            type: 'місто'   },
  { name: 'Білгород-Дністровський', region: 'Одеська',            type: 'місто'   },
  { name: 'Болград',                region: 'Одеська',            type: 'місто'   },
  { name: 'Котовськ',               region: 'Одеська',            type: 'місто'   },
  { name: 'Подільськ',              region: 'Одеська',            type: 'місто'   },
  { name: 'Роздільна',              region: 'Одеська',            type: 'місто'   },
  { name: 'Теплодар',               region: 'Одеська',            type: 'місто'   },
  { name: 'Чорноморськ',            region: 'Одеська',            type: 'місто'   },
  { name: 'Южне',                   region: 'Одеська',            type: 'місто'   },
  { name: 'Татарбунари',            region: 'Одеська',            type: 'місто'   },

  // ── Дніпропетровська область ──────────────────────────────────────────────
  { name: 'Верхньодніпровськ',      region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Вільногірськ',           region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Дніпродзержинськ',       region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Жовті Води',             region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Кам\'янське',            region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Марганець',              region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Нікополь',               region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Новомосковськ',          region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Павлоград',              region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Першотравенськ',         region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Покров',                 region: 'Дніпропетровська',   type: 'місто'   },
  { name: 'Синельникове',           region: 'Дніпропетровська',   type: 'місто'   },

  // ── Запорізька область ───────────────────────────────────────────────────
  { name: 'Бердянськ',              region: 'Запорізька',         type: 'місто'   },
  { name: 'Василівка',              region: 'Запорізька',         type: 'місто'   },
  { name: 'Гуляйполе',              region: 'Запорізька',         type: 'місто'   },
  { name: 'Енергодар',              region: 'Запорізька',         type: 'місто'   },
  { name: 'Мелітополь',             region: 'Запорізька',         type: 'місто'   },
  { name: 'Оріхів',                 region: 'Запорізька',         type: 'місто'   },
  { name: 'Пологи',                 region: 'Запорізька',         type: 'місто'   },
  { name: 'Токмак',                 region: 'Запорізька',         type: 'місто'   },

  // ── Львівська область ────────────────────────────────────────────────────
  { name: 'Борислав',               region: 'Львівська',          type: 'місто'   },
  { name: 'Броди',                  region: 'Львівська',          type: 'місто'   },
  { name: 'Городок',                region: 'Львівська',          type: 'місто'   },
  { name: 'Дрогобич',               region: 'Львівська',          type: 'місто'   },
  { name: 'Жовква',                 region: 'Львівська',          type: 'місто'   },
  { name: 'Золочів',                region: 'Львівська',          type: 'місто'   },
  { name: 'Кам\'янка-Бузька',       region: 'Львівська',          type: 'місто'   },
  { name: 'Миколаїв',               region: 'Львівська',          type: 'місто'   },
  { name: 'Мостиська',              region: 'Львівська',          type: 'місто'   },
  { name: 'Новий Розділ',           region: 'Львівська',          type: 'місто'   },
  { name: 'Пустомити',              region: 'Львівська',          type: 'смт'     },
  { name: 'Радехів',                region: 'Львівська',          type: 'місто'   },
  { name: 'Самбір',                 region: 'Львівська',          type: 'місто'   },
  { name: 'Сокаль',                 region: 'Львівська',          type: 'місто'   },
  { name: 'Стрий',                  region: 'Львівська',          type: 'місто'   },
  { name: 'Трускавець',             region: 'Львівська',          type: 'місто'   },
  { name: 'Червоноград',            region: 'Львівська',          type: 'місто'   },
  { name: 'Яворів',                 region: 'Львівська',          type: 'місто'   },

  // ── Вінницька область ────────────────────────────────────────────────────
  { name: 'Бар',                    region: 'Вінницька',          type: 'місто'   },
  { name: 'Бершадь',                region: 'Вінницька',          type: 'місто'   },
  { name: 'Гайсин',                 region: 'Вінницька',          type: 'місто'   },
  { name: 'Жмеринка',               region: 'Вінницька',          type: 'місто'   },
  { name: 'Козятин',                region: 'Вінницька',          type: 'місто'   },
  { name: 'Крижопіль',              region: 'Вінницька',          type: 'смт'     },
  { name: 'Ладижин',                region: 'Вінницька',          type: 'місто'   },
  { name: 'Могилів-Подільський',    region: 'Вінницька',          type: 'місто'   },
  { name: 'Немирів',                region: 'Вінницька',          type: 'місто'   },
  { name: 'Тульчин',                region: 'Вінницька',          type: 'місто'   },

  // ── Миколаївська область ─────────────────────────────────────────────────
  { name: 'Баштанка',               region: 'Миколаївська',       type: 'місто'   },
  { name: 'Вознесенськ',            region: 'Миколаївська',       type: 'місто'   },
  { name: 'Очаків',                 region: 'Миколаївська',       type: 'місто'   },
  { name: 'Первомайськ',            region: 'Миколаївська',       type: 'місто'   },
  { name: 'Южноукраїнськ',          region: 'Миколаївська',       type: 'місто'   },

  // ── Херсонська область ───────────────────────────────────────────────────
  { name: 'Генічеськ',              region: 'Херсонська',         type: 'місто'   },
  { name: 'Каховка',                region: 'Херсонська',         type: 'місто'   },
  { name: 'Нова Каховка',           region: 'Херсонська',         type: 'місто'   },
  { name: 'Олешки',                 region: 'Херсонська',         type: 'місто'   },
  { name: 'Скадовськ',              region: 'Херсонська',         type: 'місто'   },

  // ── Полтавська область ───────────────────────────────────────────────────
  { name: 'Гадяч',                  region: 'Полтавська',         type: 'місто'   },
  { name: 'Глобине',                region: 'Полтавська',         type: 'смт'     },
  { name: 'Зіньків',                region: 'Полтавська',         type: 'місто'   },
  { name: 'Карлівка',               region: 'Полтавська',         type: 'місто'   },
  { name: 'Кобеляки',               region: 'Полтавська',         type: 'місто'   },
  { name: 'Кременчук',              region: 'Полтавська',         type: 'місто'   },
  { name: 'Лубни',                  region: 'Полтавська',         type: 'місто'   },
  { name: 'Миргород',               region: 'Полтавська',         type: 'місто'   },
  { name: 'Пирятин',                region: 'Полтавська',         type: 'місто'   },
  { name: 'Хорол',                  region: 'Полтавська',         type: 'місто'   },

  // ── Чернігівська область ─────────────────────────────────────────────────
  { name: 'Бахмач',                 region: 'Чернігівська',       type: 'місто'   },
  { name: 'Борзна',                 region: 'Чернігівська',       type: 'місто'   },
  { name: 'Козелець',               region: 'Чернігівська',       type: 'смт'     },
  { name: 'Корюківка',              region: 'Чернігівська',       type: 'місто'   },
  { name: 'Мена',                   region: 'Чернігівська',       type: 'місто'   },
  { name: 'Ніжин',                  region: 'Чернігівська',       type: 'місто'   },
  { name: 'Новгород-Сівський',      region: 'Чернігівська',       type: 'місто'   },
  { name: 'Носівка',                region: 'Чернігівська',       type: 'місто'   },
  { name: 'Прилуки',                region: 'Чернігівська',       type: 'місто'   },
  { name: 'Семенівка',              region: 'Чернігівська',       type: 'місто'   },

  // ── Черкаська область ────────────────────────────────────────────────────
  { name: 'Золотоноша',             region: 'Черкаська',          type: 'місто'   },
  { name: 'Канів',                  region: 'Черкаська',          type: 'місто'   },
  { name: 'Корсунь-Шевченківський', region: 'Черкаська',          type: 'місто'   },
  { name: 'Монастирище',            region: 'Черкаська',          type: 'місто'   },
  { name: 'Сміла',                  region: 'Черкаська',          type: 'місто'   },
  { name: 'Тальне',                 region: 'Черкаська',          type: 'місто'   },
  { name: 'Умань',                  region: 'Черкаська',          type: 'місто'   },
  { name: 'Христинівка',            region: 'Черкаська',          type: 'місто'   },
  { name: 'Шпола',                  region: 'Черкаська',          type: 'місто'   },

  // ── Сумська область ──────────────────────────────────────────────────────
  { name: 'Глухів',                 region: 'Сумська',            type: 'місто'   },
  { name: 'Конотоп',                region: 'Сумська',            type: 'місто'   },
  { name: 'Лебедин',                region: 'Сумська',            type: 'місто'   },
  { name: 'Охтирка',                region: 'Сумська',            type: 'місто'   },
  { name: 'Ромни',                  region: 'Сумська',            type: 'місто'   },
  { name: 'Тростянець',             region: 'Сумська',            type: 'місто'   },
  { name: 'Шостка',                 region: 'Сумська',            type: 'місто'   },

  // ── Хмельницька область ──────────────────────────────────────────────────
  { name: 'Дунаївці',               region: 'Хмельницька',        type: 'місто'   },
  { name: 'Ізяслав',                region: 'Хмельницька',        type: 'місто'   },
  { name: 'Кам\'янець-Подільський', region: 'Хмельницька',        type: 'місто'   },
  { name: 'Красилів',               region: 'Хмельницька',        type: 'місто'   },
  { name: 'Нетішин',                region: 'Хмельницька',        type: 'місто'   },
  { name: 'Полонне',                region: 'Хмельницька',        type: 'місто'   },
  { name: 'Славута',                region: 'Хмельницька',        type: 'місто'   },
  { name: 'Шепетівка',              region: 'Хмельницька',        type: 'місто'   },

  // ── Житомирська область ──────────────────────────────────────────────────
  { name: 'Бердичів',               region: 'Житомирська',        type: 'місто'   },
  { name: 'Коростень',              region: 'Житомирська',        type: 'місто'   },
  { name: 'Коростишів',             region: 'Житомирська',        type: 'місто'   },
  { name: 'Малин',                  region: 'Житомирська',        type: 'місто'   },
  { name: 'Новоград-Волинський',    region: 'Житомирська',        type: 'місто'   },
  { name: 'Радомишль',              region: 'Житомирська',        type: 'місто'   },
  { name: 'Чуднів',                 region: 'Житомирська',        type: 'місто'   },

  // ── Рівненська область ───────────────────────────────────────────────────
  { name: 'Дубно',                  region: 'Рівненська',         type: 'місто'   },
  { name: 'Корець',                 region: 'Рівненська',         type: 'місто'   },
  { name: 'Костопіль',              region: 'Рівненська',         type: 'місто'   },
  { name: 'Острог',                 region: 'Рівненська',         type: 'місто'   },
  { name: 'Сарни',                  region: 'Рівненська',         type: 'місто'   },

  // ── Тернопільська область ────────────────────────────────────────────────
  { name: 'Бережани',               region: 'Тернопільська',      type: 'місто'   },
  { name: 'Борщів',                 region: 'Тернопільська',      type: 'місто'   },
  { name: 'Збараж',                 region: 'Тернопільська',      type: 'місто'   },
  { name: 'Кременець',              region: 'Тернопільська',      type: 'місто'   },
  { name: 'Монастириська',          region: 'Тернопільська',      type: 'місто'   },
  { name: 'Теребовля',              region: 'Тернопільська',      type: 'місто'   },
  { name: 'Чортків',                region: 'Тернопільська',      type: 'місто'   },

  // ── Івано-Франківська область ────────────────────────────────────────────
  { name: 'Городенка',              region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Долина',                 region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Калуш',                  region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Коломия',                region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Косів',                  region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Надвірна',               region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Снятин',                 region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Тлумач',                 region: 'Івано-Франківська',  type: 'місто'   },
  { name: 'Яремче',                 region: 'Івано-Франківська',  type: 'місто'   },

  // ── Волинська область ────────────────────────────────────────────────────
  { name: 'Горохів',                region: 'Волинська',          type: 'місто'   },
  { name: 'Камінь-Каширський',      region: 'Волинська',          type: 'місто'   },
  { name: 'Ківерці',                region: 'Волинська',          type: 'місто'   },
  { name: 'Ковель',                 region: 'Волинська',          type: 'місто'   },
  { name: 'Нововолинськ',           region: 'Волинська',          type: 'місто'   },
  { name: 'Рожище',                 region: 'Волинська',          type: 'місто'   },
  { name: 'Володимир',              region: 'Волинська',          type: 'місто'   },

  // ── Закарпатська область ─────────────────────────────────────────────────
  { name: 'Берегово',               region: 'Закарпатська',       type: 'місто'   },
  { name: 'Виноградів',             region: 'Закарпатська',       type: 'місто'   },
  { name: 'Мукачево',               region: 'Закарпатська',       type: 'місто'   },
  { name: 'Рахів',                  region: 'Закарпатська',       type: 'місто'   },
  { name: 'Свалява',                region: 'Закарпатська',       type: 'місто'   },
  { name: 'Тячів',                  region: 'Закарпатська',       type: 'місто'   },
  { name: 'Хуст',                   region: 'Закарпатська',       type: 'місто'   },
  { name: 'Міжгір\'я',              region: 'Закарпатська',       type: 'смт'     },

  // ── Чернівецька область ──────────────────────────────────────────────────
  { name: 'Вижниця',                region: 'Чернівецька',        type: 'місто'   },
  { name: 'Заставна',               region: 'Чернівецька',        type: 'місто'   },
  { name: 'Кіцмань',                region: 'Чернівецька',        type: 'місто'   },
  { name: 'Новодністровськ',        region: 'Чернівецька',        type: 'місто'   },
  { name: 'Сторожинець',            region: 'Чернівецька',        type: 'місто'   },

  // ── Кіровоградська область ───────────────────────────────────────────────
  { name: 'Гайворон',               region: 'Кіровоградська',     type: 'місто'   },
  { name: 'Знам\'янка',             region: 'Кіровоградська',     type: 'місто'   },
  { name: 'Новоукраїнка',           region: 'Кіровоградська',     type: 'місто'   },
  { name: 'Олександрія',            region: 'Кіровоградська',     type: 'місто'   },
  { name: 'Світловодськ',           region: 'Кіровоградська',     type: 'місто'   },

  // ── Луганська область (підконтрольна Україні) ────────────────────────────
  { name: 'Кремінна',               region: 'Луганська',          type: 'місто'   },
  { name: 'Лисичанськ',             region: 'Луганська',          type: 'місто'   },
  { name: 'Рубіжне',                region: 'Луганська',          type: 'місто'   },
  { name: 'Сєвєродонецьк',          region: 'Луганська',          type: 'місто'   },
  { name: 'Старобільськ',           region: 'Луганська',          type: 'місто'   },
  { name: 'Щастя',                  region: 'Луганська',          type: 'місто'   },

  // ── Донецька область (підконтрольна Україні) ─────────────────────────────
  { name: 'Авдіївка',               region: 'Донецька',           type: 'місто'   },
  { name: 'Бахмут',                 region: 'Донецька',           type: 'місто'   },
  { name: 'Волноваха',              region: 'Донецька',           type: 'місто'   },
  { name: 'Дружківка',              region: 'Донецька',           type: 'місто'   },
  { name: 'Костянтинівка',          region: 'Донецька',           type: 'місто'   },
  { name: 'Краматорськ',            region: 'Донецька',           type: 'місто'   },
  { name: 'Лиман',                  region: 'Донецька',           type: 'місто'   },
  { name: 'Маріуполь',              region: 'Донецька',           type: 'місто'   },
  { name: 'Покровськ',              region: 'Донецька',           type: 'місто'   },
  { name: 'Слов\'янськ',            region: 'Донецька',           type: 'місто'   },
  { name: 'Торецьк',                region: 'Донецька',           type: 'місто'   },
];

// Дедублікація по name (зберігаємо перший варіант)
const _seenNames = new Set();
const UA_LOCATIONS = _rawLocations.filter(loc => {
  if (_seenNames.has(loc.name)) return false;
  _seenNames.add(loc.name);
  return true;
});

// Нормалізація назви: якщо збігається з відомим населеним пунктом — повертаємо канонічну назву,
// інакше — capitalize першої літери
function normalizeLocationName(value) {
  const trimmed = value.trim();
  const match = UA_LOCATIONS.find(l => l.name.toLowerCase() === trimmed.toLowerCase());
  return match ? match.name : (trimmed.charAt(0).toUpperCase() + trimmed.slice(1));
}

// Пріоритет типів при сортуванні: місто > смт > селище > село
const _typeOrder = { 'місто': 0, 'смт': 1, 'селище': 2, 'село': 3 };

function _sortFn(a, b) {
  return (_typeOrder[a.type] ?? 9) - (_typeOrder[b.type] ?? 9)
      || a.name.localeCompare(b.name, 'uk');
}

// Фільтрація + сортування:
// 1. Київ завжди першим якщо входить в результати
// 2. startsWith-збіги (сортовані за типом і алфавітом)
// 3. contains-збіги (сортовані за типом і алфавітом)
function _filterAndSort(query) {
  const q = query.toLowerCase().trim();
  const matched = UA_LOCATIONS.filter(l => l.name.toLowerCase().includes(q));

  const kyiv       = matched.find(l => l.name === 'Київ');
  const rest       = matched.filter(l => l.name !== 'Київ');
  const startsWith = rest.filter(l =>  l.name.toLowerCase().startsWith(q)).sort(_sortFn);
  const contains   = rest.filter(l => !l.name.toLowerCase().startsWith(q)).sort(_sortFn);

  return kyiv ? [kyiv, ...startsWith, ...contains] : [...startsWith, ...contains];
}

// Debounce helper
function _debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

// Ініціалізація autocomplete для пари input + dropdown
function initCityAutocomplete(inputEl, dropdownEl) {
  let activeIdx = -1;

  const render = _debounce(function() {
    const val = inputEl.value.trim();
    activeIdx = -1;

    if (val.length < 3) {
      dropdownEl.style.display = 'none';
      return;
    }

    const results = _filterAndSort(val).slice(0, 12);

    if (!results.length) {
      dropdownEl.innerHTML = '<div class="city-autocomplete-empty">Населений пункт не знайдено</div>';
      dropdownEl.style.display = 'block';
      return;
    }

    dropdownEl.innerHTML = results.map(loc => `
      <div class="city-autocomplete-item" data-city="${loc.name}">
        <span class="city-item-name">${loc.name}</span>
        <span class="city-item-meta">
          <span class="city-item-type city-item-type--${loc.type}">${loc.type}</span>
          <span class="city-item-region">${loc.region} обл.</span>
        </span>
      </div>
    `).join('');
    dropdownEl.style.display = 'block';
  }, 200);

  function pick(cityName) {
    inputEl.value = normalizeLocationName(cityName);
    dropdownEl.style.display = 'none';
    activeIdx = -1;
    inputEl.dispatchEvent(new Event('change', { bubbles: true }));
  }

  inputEl.addEventListener('input', render);

  // Клік по пункту (mousedown перед blur)
  dropdownEl.addEventListener('mousedown', function(e) {
    const item = e.target.closest('[data-city]');
    if (item) {
      e.preventDefault(); // запобігаємо blur на input
      pick(item.dataset.city);
    }
  });

  // Клавіатурна навігація ↑↓ Enter Escape
  inputEl.addEventListener('keydown', function(e) {
    if (dropdownEl.style.display === 'none') return;
    const items = dropdownEl.querySelectorAll('.city-autocomplete-item');
    if (!items.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      pick(items[activeIdx].dataset.city);
      return;
    } else if (e.key === 'Escape') {
      dropdownEl.style.display = 'none';
      activeIdx = -1;
      return;
    } else {
      return;
    }

    items.forEach((el, i) => el.classList.toggle('city-autocomplete-item--active', i === activeIdx));
    if (activeIdx >= 0) items[activeIdx].scrollIntoView({ block: 'nearest' });
  });

  // Нормалізація та закриття при blur
  inputEl.addEventListener('blur', function() {
    if (this.value.trim()) {
      this.value = normalizeLocationName(this.value);
    }
    setTimeout(() => {
      dropdownEl.style.display = 'none';
      activeIdx = -1;
    }, 150);
  });

  // Закрити при кліку поза компонентом
  document.addEventListener('click', function(e) {
    if (!inputEl.contains(e.target) && !dropdownEl.contains(e.target)) {
      dropdownEl.style.display = 'none';
    }
  });
}
