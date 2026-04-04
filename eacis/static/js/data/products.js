// Mock PRODUCTS array (60 items) — seeded from kitchen products then generated variants
const BASE = [
  { ref: 'PRD-SLR01-0001', name: 'Two-Door Refrigerator (10 cu. ft.)', category: 'Kitchen & Cooking', price: 18000, stock: 12, rating: 4.5, reviews: 38, badge: 'Inverter', image: '/static/assets/products/2-door-refrigirator.webp' },
  { ref: 'PRD-SLR01-0002', name: 'Single Door Refrigerator (6 cu. ft.)', category: 'Kitchen & Cooking', price: 8500, stock: 20, rating: 4.2, reviews: 22, badge: null, image: '/static/assets/products/single-door-ref.webp' },
  { ref: 'PRD-SLR01-0003', name: 'Inverter Chest Freezer', category: 'Kitchen & Cooking', price: 11000, stock: 8, rating: 4.4, reviews: 15, badge: 'Inverter', image: '/static/assets/products/inverted-chest-freezer.webp' },
  { ref: 'PRD-SLR01-0004', name: 'Gas Range with Oven (4 Burners)', category: 'Kitchen & Cooking', price: 14500, stock: 6, rating: 4.6, reviews: 44, badge: 'New', image: '/static/assets/products/gas-range-with-oven-4-burners.webp' },
  { ref: 'PRD-SLR01-0005', name: 'Induction Cooker (Double Zone)', category: 'Kitchen & Cooking', price: 4500, stock: 30, rating: 4.3, reviews: 19, badge: null, image: '/static/assets/products/induction-cooker-double.png' },
  { ref: 'PRD-SLR01-0006', name: 'Single Burner Induction Cooker', category: 'Kitchen & Cooking', price: 1800, stock: 50, rating: 4.1, reviews: 12, badge: null, image: '/static/assets/products/single-burner-induction-cooker.webp' },
  { ref: 'PRD-SLR01-0007', name: 'Microwave Oven (20L)', category: 'Kitchen & Cooking', price: 3200, stock: 25, rating: 4.2, reviews: 25, badge: null, image: '/static/assets/products/microwave-oven.jfif' },
  { ref: 'PRD-SLR01-0008', name: 'Air Fryer (5L)', category: 'Kitchen & Cooking', price: 2800, stock: 40, rating: 4.0, reviews: 40, badge: null, image: '/static/assets/products/air-fryer.jfif' },
  { ref: 'PRD-SLR01-0009', name: 'Electric Oven/Rotisserie (35L)', category: 'Kitchen & Cooking', price: 4000, stock: 10, rating: 4.0, reviews: 10, badge: null, image: '/static/assets/products/electric-oven-rotisserie.webp' },
  { ref: 'PRD-SLR01-0010', name: 'Rice Cooker (1.8L)', category: 'Kitchen & Cooking', price: 1500, stock: 60, rating: 4.1, reviews: 42, badge: null, image: '/static/assets/products/rice-cooker.jpg' },
  { ref: 'PRD-SLR01-0011', name: 'Electric Kettle (1.7L)', category: 'Kitchen & Cooking', price: 800, stock: 80, rating: 4.2, reviews: 18, badge: null, image: '/static/assets/products/electric-kettle.webp' },
  { ref: 'PRD-SLR01-0012', name: 'Stand Mixer', category: 'Kitchen & Cooking', price: 4500, stock: 15, rating: 4.3, reviews: 15, badge: null, image: '/static/assets/products/stand-mixer.jfif' },
  { ref: 'PRD-SLR01-0013', name: 'Electric Food Processor', category: 'Kitchen & Cooking', price: 2200, stock: 20, rating: 4.1, reviews: 9, badge: null, image: '/static/assets/products/electric-food-processor.jfif' },
  { ref: 'PRD-SLR01-0014', name: 'Blender (1.5L)', category: 'Kitchen & Cooking', price: 1600, stock: 25, rating: 4.0, reviews: 14, badge: null, image: '/static/assets/products/blender.jfif' },
  { ref: 'PRD-SLR01-0015', name: 'Coffee Maker (Drip type)', category: 'Kitchen & Cooking', price: 1200, stock: 30, rating: 4.1, reviews: 8, badge: null, image: '/static/assets/products/coffee-maker.jfif' },
  { ref: 'PRD-SLR01-0016', name: 'Espresso Machine', category: 'Kitchen & Cooking', price: 6500, stock: 8, rating: 4.4, reviews: 8, badge: null, image: '/static/assets/products/espresso-machine.jfif' },
  { ref: 'PRD-SLR01-0017', name: 'Bread Toaster (2-Slice)', category: 'Kitchen & Cooking', price: 900, stock: 40, rating: 3.9, reviews: 22, badge: null, image: '/static/assets/products/bread-toaster.jfif' },
  { ref: 'PRD-SLR01-0018', name: 'Sandwich Maker/Waffle Iron', category: 'Kitchen & Cooking', price: 1100, stock: 35, rating: 4.0, reviews: 12, badge: null, image: '/static/assets/products/sandwich-maker.jfif' },
  { ref: 'PRD-SLR01-0019', name: 'Juice Extractor', category: 'Kitchen & Cooking', price: 2500, stock: 20, rating: 4.2, reviews: 10, badge: null, image: '/static/assets/products/juice-extractor.jfif' },
  { ref: 'PRD-SLR01-0020', name: 'Slow Cooker (3.5L)', category: 'Kitchen & Cooking', price: 1800, stock: 22, rating: 4.1, reviews: 6, badge: null, image: '/static/assets/products/slow-cooker.jfif' },
  { ref: 'PRD-SLR01-0021', name: 'Dishwasher (Countertop)', category: 'Kitchen & Cooking', price: 12000, stock: 6, rating: 4.1, reviews: 6, badge: null, image: '/static/assets/products/dishwasher-countertop.jfif' },
  { ref: 'PRD-SLR01-0022', name: 'Water Dispenser (Top Load)', category: 'Kitchen & Cooking', price: 3500, stock: 18, rating: 4.0, reviews: 9, badge: null, image: '/static/assets/products/water-dispenser.webp' }
];

// generate additional variants to reach 60
const PRODUCTS = BASE.slice();
let idx = BASE.length;
const categories = ['Laundry & Cleaning','Cooling & Air Quality','Home Entertainment','Gadgets','Kitchen & Cooking'];
while (PRODUCTS.length < 60) {
  idx++;
  const cat = categories[(idx + 2) % categories.length];
  const price = Math.round((1000 + (idx * 123) % 22000)/100)*100;
  PRODUCTS.push({
    ref: `PRD-SLR01-${String(220 + idx).padStart(4,'0')}`,
    name: `Product ${idx} Sample Item`,
    category: cat,
    price: price,
    stock: Math.max(0, (idx * 7) % 60),
    rating: (3 + (idx % 20)/10).toFixed(1),
    reviews: (idx * 3) % 200,
    badge: (idx % 7 === 0) ? 'New' : null,
    image: PRODUCTS[(idx-1) % BASE.length].image
  });
}

// expose globally
window.PRODUCTS = PRODUCTS;
